"""Tests for pyhon.diagnose: the data archive is written without blocking the event loop."""

import asyncio
import json
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from pyhon import diagnose

TOPICS = {
    "commands",
    "attributes",
    "command_history",
    "statistics",
    "maintenance",
    "appliance_data",
}


class FakeAPI:
    """Stands in for HonAPI: one coroutine per topic the archive requests."""

    async def load_commands(self, appliance: Any) -> Dict[str, Any]:
        return {"startProgram": {"macAddress": "12-34-56-78-9A-BC"}}

    async def load_attributes(self, appliance: Any) -> Dict[str, Any]:
        return {"shadow": {"parameters": {"machMode": {"parNewVal": "1"}}}}

    async def load_command_history(self, appliance: Any) -> List[Any]:
        return []

    async def load_statistics(self, appliance: Any) -> Dict[str, Any]:
        return {}

    async def load_maintenance(self, appliance: Any) -> Dict[str, Any]:
        return {}


def fake_appliance() -> Any:
    return SimpleNamespace(
        api=FakeAPI(),
        appliance_type="WM",
        model_id=1234,
        info={"attributes": {"serialNumber": "ABC123"}, "nickName": "Washer"},
    )


def test_zip_archive_writes_anonymised_archive(tmp_path: Path) -> None:
    name = asyncio.run(diagnose.zip_archive(fake_appliance(), tmp_path, anonymous=True))

    assert name == "wm_1234.zip"
    archive = tmp_path / name
    assert archive.is_file()
    assert not (tmp_path / "wm_1234").exists(), "working directory is removed"
    with zipfile.ZipFile(archive) as zipped:
        assert {Path(n).stem for n in zipped.namelist()} == TOPICS
        commands = json.loads(zipped.read("commands.json"))
        appliance = json.loads(zipped.read("appliance_data.json"))
    assert commands["startProgram"]["macAddress"] == "xx-xx-xx-xx-xx-xx"
    # the nick name is anonymised, and HonAppliance expects the attributes in list form
    assert appliance["nickName"] == "Xxxxxx"
    assert appliance["attributes"][0]["parName"] == "serialNumber"


def test_file_io_runs_off_the_event_loop(tmp_path: Path, monkeypatch: Any) -> None:
    threads: List[threading.Thread] = []
    original_write, original_zip = diagnose._write_files, diagnose._zip_directory

    def spy_write(*args: Any, **kwargs: Any) -> List[Path]:
        threads.append(threading.current_thread())
        return original_write(*args, **kwargs)

    def spy_zip(*args: Any, **kwargs: Any) -> str:
        threads.append(threading.current_thread())
        return original_zip(*args, **kwargs)

    monkeypatch.setattr(diagnose, "_write_files", spy_write)
    monkeypatch.setattr(diagnose, "_zip_directory", spy_zip)

    async def run() -> threading.Thread:
        await diagnose.zip_archive(fake_appliance(), tmp_path, anonymous=False)
        return threading.current_thread()

    loop_thread = asyncio.run(run())

    assert len(threads) == 2, "directory/JSON writing and zipping each ran once"
    assert all(thread is not loop_thread for thread in threads)
