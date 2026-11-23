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
