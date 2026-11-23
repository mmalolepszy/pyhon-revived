import json
import logging
from pathlib import Path

import pytest

from pyhon.appliance import HonAppliance
from pyhon.connection.api import TestAPI as FakeAPI

APPLIANCE = {"applianceTypeName": "DW", "applianceModelId": 1, "nickName": "DW"}


@pytest.fixture(name="appliance")
async def fixture_appliance(tmp_path: Path) -> HonAppliance:
    data = tmp_path / "dw_1"
    data.mkdir()
    (data / "appliance_data.json").write_text(json.dumps(APPLIANCE))
    commands = {"applianceModel": {"options": {"opt3": "halfLoad", "opt5": "openDoor"}}}
    (data / "commands.json").write_text(json.dumps(commands))
    parameters = {"prCode": "8", "openDoor": "1", "halfLoad": "0", "prPosition": "1"}
    attributes = {
        "shadow": {"parameters": {k: {"parNewVal": v} for k, v in parameters.items()}}
    }
    (data / "attributes.json").write_text(json.dumps(attributes))
    appliance = HonAppliance(FakeAPI(tmp_path), dict(APPLIANCE))
    await appliance.load_commands()
    await appliance.load_attributes()
    return appliance


def values(appliance: HonAppliance) -> dict[str, str]:
    return {k: str(v) for k, v in appliance.attributes["parameters"].items()}


def change(name: str, old: str, new: str) -> dict[str, str]:
    return {"parName": name, "parOldVal": old, "parNewVal": new}


async def test_option_alias_updates_option(appliance: HonAppliance) -> None:
    appliance.update_parameters([change("opt5", "1", "0")])
    assert values(appliance)["openDoor"] == "0"


async def test_mixed_names_and_aliases(appliance: HonAppliance) -> None:
    appliance.update_parameters(
        [
            change("prCode", "8", "27"),
            change("opt5", "1", "0"),
            change("prPosition", "1", "2"),
        ]
    )
    assert values(appliance) == {
        "prCode": "27",
        "openDoor": "0",
        "halfLoad": "0",
        "prPosition": "2",
    }


async def test_unknown_parameter_is_skipped(
    appliance: HonAppliance, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        appliance.update_parameters(
            [change("unknownPar", "0", "1"), change("prCode", "8", "27")]
        )
    assert values(appliance)["prCode"] == "27"
    assert "unknown parameter unknownPar" in caplog.text
