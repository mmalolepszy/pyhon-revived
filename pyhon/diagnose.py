import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Tuple

from pyhon import printer

if TYPE_CHECKING:
    from pyhon.appliance import HonAppliance


def anonymize_data(data: str) -> str:
    default_date = "1970-01-01T00:00:00.0Z"
    default_mac = "xx-xx-xx-xx-xx-xx"
    data = re.sub("[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}", default_mac, data)
    data = re.sub("[\\d-]{10}T[\\d:]{8}(.\\d+)?Z", default_date, data)
    data = re.sub(
        "\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}", "1970-01-01 00:00:00", data
    )
    # hOn (Salesforce) account ids, wherever they appear
    data = re.sub(
        '"001[A-Za-z0-9]{12}([A-Za-z0-9]{3})?"',
        lambda m: re.sub("[A-Za-z0-9]", "x", m.group(0)),
        data,
    )
    for sensible in [
        "serialNumber",
        "code",
        "nickName",
        "mobileId",
        "PK",
        "SK",
        "lat",
        "lng",
        "principalUserId",
        "secondaryUserId",
        "sfPersonAccountId",
    ]:
        for match in re.findall(f'"{sensible}.*?":\\s"?(.+?)"?,?\\n', data):
            data = data.replace(match, _mask_value(match))
    return data


def _mask_value(value: str) -> str:
    """Mask letters and digits of a JSON-encoded string value.

    Escape sequences are kept valid: a \\uXXXX escape (a non-ASCII character)
    is masked as one "x", other escapes (\\n, \\", \\\\ ...) are left as they are.
    """

    def mask(match: "re.Match[str]") -> str:
        text = match.group(0)
        if text.startswith("\\u"):
            return "x"
        if text.startswith("\\"):
            return text
        if text.islower():
            return "x"
        if text.isupper():
            return "X"
        return "1"

    return re.sub(r"\\u[0-9A-Fa-f]{4}|\\.|[a-z]|[A-Z]|\d", mask, value)


async def load_data(appliance: "HonAppliance", topic: str) -> Tuple[str, str]:
    return topic, await getattr(appliance.api, f"load_{topic}")(appliance)


def write_to_json(data: str, topic: str, path: Path, anonymous: bool = False) -> Path:
    json_data = json.dumps(data, indent=4)
    if anonymous:
        json_data = anonymize_data(json_data)
    file = path / f"{topic}.json"
    with open(file, "w", encoding="utf-8") as json_file:
        json_file.write(json_data)
    return file


async def appliance_data(
    appliance: "HonAppliance", path: Path, anonymous: bool = False
) -> List[Path]:
    requests = [
        "commands",
        "attributes",
        "command_history",
        "statistics",
        "maintenance",
    ]
    path /= f"{appliance.appliance_type}_{appliance.model_id}".lower()
    path.mkdir(parents=True, exist_ok=True)
    api_data: List[Tuple[str, Any]] = list(
        await asyncio.gather(*[load_data(appliance, name) for name in requests])
    )
    # appliance_data.json is the appliance record from the appliance list (what
    # TestAPI.load_appliances reads back). The appliance-model endpoint used
    # before gives an empty result in current exports.
    # HonAppliance turns "attributes" into a dict; store the list form it expects.
    info = dict(appliance.info)
    if isinstance(info.get("attributes"), dict):
        info["attributes"] = [
            {"parName": name, "parValue": value}
            for name, value in info["attributes"].items()
        ]
    api_data.append(("appliance_data", info))
    return [write_to_json(data, topic, path, anonymous) for topic, data in api_data]


async def zip_archive(
    appliance: "HonAppliance", path: Path, anonymous: bool = False
) -> str:
    data = await appliance_data(appliance, path, anonymous)
    archive = data[0].parent
    shutil.make_archive(str(archive), "zip", archive)
    shutil.rmtree(archive)
    return f"{archive.stem}.zip"


def yaml_export(appliance: "HonAppliance", anonymous: bool = False) -> str:
    data = {
        "attributes": appliance.attributes.copy(),
        "appliance": appliance.info,
        "statistics": appliance.statistics,
        "additional_data": appliance.additional_data,
    }
    data |= {n: c.parameter_groups for n, c in appliance.commands.items()}
    extra = {n: c.data for n, c in appliance.commands.items() if c.data}
    if extra:
        data |= {"extra_command_data": extra}
    if anonymous:
        for sensible in ["serialNumber", "coords"]:
            data.get("appliance", {}).pop(sensible, None)
    result = printer.pretty_print({"data": data})
    if commands := printer.create_commands(appliance.commands):
        result += printer.pretty_print({"commands": commands})
    if rules := printer.create_rules(appliance.commands):
        result += printer.pretty_print({"rules": rules})
    if anonymous:
        result = anonymize_data(result)
    return result
