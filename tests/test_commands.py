from copy import copy
from types import SimpleNamespace

from pyhon.commands import HonCommand


def make_command() -> HonCommand:
    attributes = {
        "parameters": {
            "temp": {
                "typology": "range",
                "minimumValue": "0",
                "maximumValue": "40",
                "incrementValue": "10",
                "defaultValue": "20",
            }
        }
    }
    return HonCommand("startProgram", attributes, SimpleNamespace(zone=0))  # type: ignore[arg-type]


def test_copy_has_same_parameter_values() -> None:
    command = make_command()
    assert copy(command).parameter_value == command.parameter_value


def test_copy_changes_do_not_leak_to_original() -> None:
    command = make_command()
    copied = copy(command)
    copied.parameters["temp"].value = 30
    assert command.parameters["temp"].value == 20


def make_command_without_defaults() -> HonCommand:
    attributes = {
        "parameters": {
            "optionalEnum": {"typology": "enum", "mandatory": 0, "enumValues": [2, 4]},
            "optionalRange": {
                "typology": "range",
                "mandatory": 0,
                "minimumValue": "1",
                "maximumValue": "5",
                "incrementValue": "1",
            },
            "optionalFixed": {"typology": "fixed", "mandatory": 0},
            "mandatoryEnum": {"typology": "enum", "mandatory": 1, "enumValues": [2, 4]},
            "optionalDefault": {
                "typology": "enum",
                "mandatory": 0,
                "enumValues": [2, 4],
                "defaultValue": "4",
            },
        }
    }
    return HonCommand("startProgram", attributes, SimpleNamespace(zone=0))  # type: ignore[arg-type]


def test_optional_parameters_without_value_are_not_sent() -> None:
    command = make_command_without_defaults()
    assert set(command.parameter_groups["parameters"]) == {
        "mandatoryEnum",
        "optionalDefault",
    }


def test_optional_parameters_are_sent_once_set() -> None:
    command = make_command_without_defaults()
    command.parameters["optionalEnum"].value = "2"
    command.parameters["optionalRange"].value = 3
    command.parameters["optionalFixed"].value = "1"
    parameters = command.parameter_groups["parameters"]
    assert parameters["optionalEnum"] == "2"
    assert parameters["optionalRange"] == "3"
    assert parameters["optionalFixed"] == "1"


def test_reset_clears_set_value() -> None:
    command = make_command_without_defaults()
    command.parameters["optionalEnum"].value = "2"
    command.reset()
    assert "optionalEnum" not in command.parameter_groups["parameters"]
