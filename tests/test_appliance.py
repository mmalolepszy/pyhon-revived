import json
import logging
from pathlib import Path
from typing import Any

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
                    "lightStatus": {
                        "typology": "range",
                        "mandatory": 0,
                        "minimumValue": "0",
                        "maximumValue": "1",
                        "incrementValue": "1",
                        "defaultValue": "0",
                    },
                    "humiditySel": {
                        "typology": "range",
                        "mandatory": 0,
                        "minimumValue": "30",
                        "maximumValue": "80",
                        "incrementValue": "1",
                        "defaultValue": "30",
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
    parameters = {
        "tempSel": "24",
        "windSpeed": "2",
        "humiditySel": "40",
        "mqttEndpoint": "test",
    }
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


async def test_reported_value_overrides_program_limits(
    settings_appliance: HonAppliance,
) -> None:
    await settings_appliance.load_attributes()
    settings = settings_appliance.commands["settings"].settings
    settings["windSpeed"].values = ["2"]
    settings["tempSel"].min = settings["tempSel"].max = 24
    settings_appliance.update_parameters(
        [change("windSpeed", "2", "1"), change("tempSel", "24", "20")]
    )
    settings_appliance.sync_params_to_command("settings")
    assert settings["windSpeed"].value == "1"
    assert settings["windSpeed"].values == ["1", "2", "5"]
    assert settings["tempSel"].value == 20
    assert (settings["tempSel"].min, settings["tempSel"].max) == (16, 30)


async def test_allowed_reported_value_keeps_program_limits(
    settings_appliance: HonAppliance,
) -> None:
    await settings_appliance.load_attributes()
    settings = settings_appliance.commands["settings"].settings
    settings["tempSel"].max = 25
    settings_appliance.update_parameters([change("tempSel", "24", "20")])
    settings_appliance.sync_params_to_command("settings")
    assert settings["tempSel"].value == 20
    assert settings["tempSel"].max == 25


async def test_invalid_reported_value_is_skipped(
    settings_appliance: HonAppliance,
) -> None:
    await settings_appliance.load_attributes()
    settings = settings_appliance.commands["settings"].settings
    settings_appliance.update_parameters([change("windSpeed", "2", "9")])
    settings_appliance.sync_params_to_command("settings")
    assert settings["windSpeed"].value == "2"


@pytest.mark.parametrize(
    ("reported", "expected"),
    # A wine cellar reports whole °F: 8 °C -> 46 °F -> 7.8, 16 °C -> 61 °F -> 16.1
    [("20.6", 21), ("16.1", 16), ("23.5", 24), ("24", 24)],
)
async def test_reported_value_rounds_to_step(
    settings_appliance: HonAppliance, reported: str, expected: int
) -> None:
    await settings_appliance.load_attributes()
    settings = settings_appliance.commands["settings"].settings
    settings_appliance.update_parameters([change("tempSel", "24", reported)])
    settings_appliance.sync_params_to_command("settings")
    assert settings["tempSel"].value == expected
    assert str(settings["tempSel"].intern_value) == str(expected)


async def test_reported_value_rounds_to_fractional_step(
    settings_appliance: HonAppliance,
) -> None:
    await settings_appliance.load_attributes()
    settings = settings_appliance.commands["settings"].settings
    settings["tempSel"].step = 0.5
    for reported, expected in (("20.7", 20.5), ("20.8", 21), ("17.2", 17)):
        settings_appliance.update_parameters([change("tempSel", "24", reported)])
        settings_appliance.sync_params_to_command("settings")
        assert settings["tempSel"].value == expected


async def test_rounded_value_outside_program_limits(
    settings_appliance: HonAppliance,
) -> None:
    await settings_appliance.load_attributes()
    settings = settings_appliance.commands["settings"].settings
    settings["tempSel"].max = 25
    settings_appliance.update_parameters([change("tempSel", "24", "27.8")])
    settings_appliance.sync_params_to_command("settings")
    assert settings["tempSel"].value == 28
    assert settings["tempSel"].max == 30


@pytest.fixture(name="sent")
def fixture_sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send_command(
        _api: Any, _appliance: Any, _command: str, parameters: Any, *_args: Any
    ) -> bool:
        sent.append(dict(parameters))
        return True

    monkeypatch.setattr(FakeAPI, "send_command", send_command)
    return sent


async def test_send_specific_sends_changed_and_mandatory(
    settings_appliance: HonAppliance, sent: list[dict[str, Any]]
) -> None:
    await settings_appliance.load_attributes()
    command = settings_appliance.commands["settings"]
    command.settings["lightStatus"].value = 1
    await command.send_specific(["lightStatus"])
    assert sent == [{"tempSel": "24", "windSpeed": "2", "lightStatus": "1"}]


async def test_send_specific_leaves_out_unchanged_optional(
    settings_appliance: HonAppliance, sent: list[dict[str, Any]]
) -> None:
    await settings_appliance.load_attributes()
    await settings_appliance.commands["settings"].send_specific(["tempSel"])
    assert sent == [{"tempSel": "24", "windSpeed": "2"}]


async def test_state_follows_only_sent_parameters(
    settings_appliance: HonAppliance,
    sent: list[dict[str, Any]],  # pylint: disable=unused-argument
) -> None:
    await settings_appliance.load_attributes()
    command = settings_appliance.commands["settings"]
    command.settings["tempSel"].value = 25
    command.settings["humiditySel"].value = 60
    await command.send_specific(["tempSel"])
    assert values(settings_appliance)["tempSel"] == "25"
    assert values(settings_appliance)["humiditySel"] == "40"
