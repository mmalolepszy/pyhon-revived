#!/usr/bin/env python
import argparse
import os
import asyncio
import json
import logging
import sys
from getpass import getpass
from pathlib import Path
from typing import Tuple, Dict, Any

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position
from pyhon import Hon, HonAPI, diagnose, printer

_LOGGER = logging.getLogger(__name__)

log_level = logging.DEBUG if os.getenv("PYHON_DEBUG") else logging.WARNING
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def get_arguments() -> Dict[str, Any]:
    """Get parsed arguments."""
    parser = argparse.ArgumentParser(description="pyhOn: Command Line Utility")
    parser.add_argument("-u", "--user", help="user for haier hOn account")
    parser.add_argument("-p", "--password", help="password for haier hOn account")
    subparser = parser.add_subparsers(title="commands", metavar="COMMAND")
    keys = subparser.add_parser("keys", help="print as key format")
    keys.set_defaults(command="keys")
    keys.add_argument("--all", help="print also full keys", action="store_true")
    export = subparser.add_parser("export", help="export pyhon data")
    export.set_defaults(command="export")
    export.add_argument("--zip", help="create zip archive", action="store_true")
    export.add_argument("--anonymous", help="anonymize data", action="store_true")
    export.add_argument("directory", nargs="?", default=Path().cwd())
    translation = subparser.add_parser(
        "translate", help="print available translation keys"
    )
    translation.add_argument(
        "translate", help="language (de, en, fr...)", metavar="LANGUAGE"
    )
    translation.add_argument("--json", help="print as json", action="store_true")
    parser.add_argument("-i", "--import", help="import pyhon data", nargs="?")
    parser.add_argument("-o", "--output", help="save output to file")
    return vars(parser.parse_args())


async def translate(language: str, json_output: bool = False) -> None:
    async with HonAPI(anonymous=True) as hon:
        keys = await hon.translation_keys(language)
    if json_output:
        print(json.dumps(keys, indent=4))
    else:
        clean_keys = (
            json.dumps(keys)
            .replace("\\n", "\\\\n")
            .replace("\\\\r", "")
            .replace("\\r", "")
        )
        keys = json.loads(clean_keys)
        print(printer.pretty_print(keys))


def get_login_data(args: Dict[str, str]) -> Tuple[str, str]:
    if not (user := args["user"]):
        user = input("User for hOn account: ")
    if not (password := args["password"]):
        password = getpass("Password for hOn account: ")
    return user, password


async def main() -> None:
    args = get_arguments()
    if path := args.get("output"):
        with open(path, "w", encoding="utf-8"):
            pass
    if language := args.get("translate"):
        await translate(language, json_output=args.get("json", ""))
        return
    test_data_path = Path(path) if (path := args.get("import", "")) else None
    async with Hon(*get_login_data(args), test_data_path=test_data_path) as hon:
        for device in hon.appliances:
            if args.get("command") == "export":
                anonymous = args.get("anonymous", False)
                path = Path(args.get("directory", "."))
                if not args.get("zip"):
                    for file in await diagnose.appliance_data(device, path, anonymous):
                        print(f"Created {file}")
                else:
                    archive = await diagnose.zip_archive(device, path, anonymous)
                    print(f"Created {archive}")
                continue
            title = (
                f"{'=' * 10} {device.appliance_type} - {device.nick_name} {'=' * 10}"
            )
            if args.get("command") == "keys":
                print(title)
                data = device.data.copy()
                attr = "get" if args.get("all") else "pop"
                print(
                    printer.key_print(getattr(data["attributes"], attr)("parameters"))
                )
                print(printer.key_print(getattr(data, attr)("appliance")))
                print(printer.key_print(data))
                print(
                    printer.pretty_print(
                        printer.create_commands(device.commands, concat=True)
                    )
                )
            else:
                output = diagnose.yaml_export(device)
                if path := args.get("output"):
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(f"{title}\n")
                        f.write(output)
                    print(f"Appended {device.nick_name} to {path}")
                else:
                    print(title)
                    print(output)


def start() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Aborted.")


if __name__ == "__main__":
    start()
