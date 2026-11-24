import json
import logging
from pathlib import Path

import pytest

from pyhon.appliance import HonAppliance
from pyhon.connection.api import TestAPI as FakeAPI
from pyhon.parameter.enum import HonParameterEnum

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


def enum(allowed: list[int], default: str | None = None) -> HonParameterEnum:
    attributes = {"typology": "enum", "enumValues": allowed}
    if default is not None:
        attributes["defaultValue"] = default
    return HonParameterEnum("key", attributes, "parameters")


async def test_sync_skips_parameter_without_value(appliance: HonAppliance) -> None:
    source, target = enum([8, -16]), enum([2, 4, -18], default="-18")
    appliance.sync_parameter(source, target)
    assert target.value == "-18"
    assert target.values == ["2", "4", "-18"]


async def test_sync_copies_value_and_allowed_values(appliance: HonAppliance) -> None:
    source, target = enum([8, -16], default="-16"), enum([2, 8], default="8")
    appliance.sync_parameter(source, target)
    assert target.value == "-16"
    assert target.values == ["8", "-16"]


@pytest.fixture(name="settings_appliance")
async def fixture_settings_appliance(tmp_path: Path) -> HonAppliance:
    data = tmp_path / "ac_1"
    data.mkdir()
    command = {"description": "", "protocolType": ""}
    commands = {
        "settings": {
            "setParameters": {
                **command,
                "parameters": {
                    "tempSel": {
                        "typology": "range",
                        "mandatory": 1,
                        "minimumValue": "16",
                        "maximumValue": "30",
                        "incrementValue": "1",
                        "defaultValue": "22",
                    },
                    "windSpeed": {
                        "typology": "enum",
                        "mandatory": 1,
                        "enumValues": [1, 2, 5],
                        "defaultValue": "5",
                    },
                },
            },
            "setConfig": {
                **command,
                "parameters": {"mqttEndpoint": {"typology": "fixed", "mandatory": 0}},
            },
        }
    }
    (data / "commands.json").write_text(json.dumps(commands))
    parameters = {"tempSel": "24", "windSpeed": "2", "mqttEndpoint": "test"}
    attributes = {
        "shadow": {"parameters": {k: {"parNewVal": v} for k, v in parameters.items()}}
    }
    (data / "attributes.json").write_text(json.dumps(attributes))
    info = {"applianceTypeName": "AC", "applianceModelId": 1, "nickName": "AC"}
    appliance = HonAppliance(FakeAPI(tmp_path), info)
    await appliance.load_commands()
    return appliance


async def test_settings_follow_loaded_attributes(
    settings_appliance: HonAppliance,
) -> None:
    settings = settings_appliance.commands["settings"].settings
    assert settings["tempSel"].value == 22
    assert settings["windSpeed"].value == "5"

    await settings_appliance.load_attributes()
    assert settings["tempSel"].value == 24
    assert settings["windSpeed"].value == "2"


async def test_settings_sync_ignores_other_categories(
    settings_appliance: HonAppliance,
) -> None:
    await settings_appliance.load_attributes()
    settings_appliance.sync_params_to_command("settings")
    assert "mqttEndpoint" not in settings_appliance.commands["settings"].settings
