import json
from typing import Any, Dict, List

from pyhon.appliance import HonAppliance
from pyhon.commands import HonCommand
from pyhon.duration import (
    calculate_hqd_duration,
    is_hqd_duration_supported,
    normalize_model_attributes,
)


def _wm_hqd_model_attributes() -> List[Dict[str, Any]]:
    """Minimal anonymized HQD washing machine applianceModel.attributes fixture."""
    main_wash = {
        "prCode": {
            "71": 60,
            "121": 24,
            "default": {
                "mainWashTime": {
                    "0": 0,
                    "default": {
                        "suggestedLoadW": {
                            "undefined": {
                                "prCode": {"default": "mainWashTime+#finalSpinDuration+2"}
                            },
                            "default": {
                                "#suggestedLoadWKg": {
                                    "4": {
                                        "temp": {
                                            "0": {
                                                "prCode": {
                                                    "default": "mainWashTime+#finalSpinDuration+7"
                                                }
                                            },
                                            "30": {
                                                "prCode": {
                                                    "default": "mainWashTime+#finalSpinDuration+17"
                                                }
                                            },
                                            "40": {
                                                "prCode": {
                                                    "default": "mainWashTime+#finalSpinDuration+27"
                                                }
                                            },
                                            "60": {
                                                "prCode": {
                                                    "default": "mainWashTime+#finalSpinDuration+42"
                                                }
                                            },
                                        }
                                    },
                                    "8": {
                                        "temp": {
                                            "40": {
                                                "prCode": {
                                                    "default": "mainWashTime+#finalSpinDuration+37"
                                                }
                                            },
                                        }
                                    },
                                }
                            },
                        }
                    },
                }
            },
        }
    }
    rinse = {
        "prCode": {
            "71": 0,
            "121": 0,
            "default": {
                "rinseIterations": {
                    "0": 0,
                    "default": {
                        "spinSpeed": {
                            "0": "(rinseIterationTime+2)*(rinseIterations-1)+rinseIterationTime",
                            "default": {
                                "prCode": {
                                    "72": {
                                        "400|600|800|1000": "(rinseIterationTime+3)*(rinseIterations-1)+rinseIterationTime",
                                        "1200|1400": "(rinseIterationTime+5)*(rinseIterations-1)+rinseIterationTime",
                                    },
                                    "default": {
                                        "spinSpeed": {
                                            "400|600|800|1000": "(rinseIterationTime+5)*(rinseIterations-1)+rinseIterationTime",
                                            "1200|1400": "(rinseIterationTime+7)*(rinseIterations-1)+rinseIterationTime",
                                        }
                                    },
                                }
                            },
                        }
                    },
                }
            },
        }
    }
    return [
        {"parName": "platform", "parValue": "HQD"},
        {"parName": "loadCapacityWash", "parValue": "8"},
        {
            "parName": "remainingTime",
            "parValue": (
                "remainingTimePrewash+remainingTimeMainWash+"
                "remainingTimeRinse+remainingTimeFinalSpin+remainingTimeAntiWrinkle"
            ),
        },
        {
            "parName": "finalSpinDuration",
            "parValue": json.dumps(
                {"spinSpeed": {"0": 0, "default": {"prCode": {"72": 1, "default": 3}}}}
            ),
        },
        {
            "parName": "remainingTimePrewash",
            "parValue": json.dumps(
                {
                    "prCode": {
                        "71": 0,
                        "121": 0,
                        "default": {
                            "haier_SoakPrewashSelection": {
                                "0": 0,
                                "default": "#finalSpinDuration+17",
                            }
                        },
                    }
                }
            ),
        },
        {
            "parName": "suggestedLoadWKg",
            "parValue": json.dumps(
                {
                    "round": 0,
                    "suggestedLoadW": {
                        "RL100": "#loadCapacityWash*1",
                        "RL50": "#loadCapacityWash*0.5",
                        "RL17": "#loadCapacityWash*0.17",
                    },
                }
            ),
        },
        {"parName": "remainingTimeMainWash", "parValue": json.dumps(main_wash)},
        {"parName": "remainingTimeRinse", "parValue": json.dumps(rinse)},
        {
            "parName": "remainingTimeFinalSpin",
            "parValue": json.dumps(
                {
                    "prCode": {
                        "71": 0,
                        "121": 0,
                        "default": {
                            "#finalSpinDuration": {
                                "0": 0,
                                "default": "#finalSpinDuration+2",
                            }
                        },
                    }
                }
            ),
        },
        {
            "parName": "remainingTimeAntiWrinkle",
            "parValue": json.dumps(
                {"prCode": {"71": 0, "121": 0, "default": {"antiWrinkle": {"0": 0, "default": 1}}}}
            ),
        },
    ]


def _make_dark_program_data(include_static_remaining: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "description": "Start program",
        "protocolType": "MQTT",
        "parameters": {
            "prCode": {"category": "command", "typology": "fixed", "mandatory": 1, "fixedValue": "116"},
            "temp": {
                "category": "command",
                "typology": "enum",
                "mandatory": 1,
                "defaultValue": "30",
                "enumValues": ["0", "30", "40", "60"],
            },
            "spinSpeed": {
                "category": "command",
                "typology": "enum",
                "mandatory": 1,
                "defaultValue": "800",
                "enumValues": ["0", "400", "800", "1200"],
            },
            "mainWashTime": {
                "category": "command",
                "typology": "range",
                "mandatory": 1,
                "defaultValue": "10",
                "minimumValue": "5",
                "maximumValue": "30",
                "incrementValue": "5",
            },
            "rinseIterations": {
                "category": "command",
                "typology": "range",
                "mandatory": 1,
                "defaultValue": "2",
                "minimumValue": "0",
                "maximumValue": "5",
                "incrementValue": "1",
            },
            "rinseIterationTime": {
                "category": "command",
                "typology": "fixed",
                "mandatory": 1,
                "fixedValue": "9",
            },
            "haier_SoakPrewashSelection": {
                "category": "command",
                "typology": "range",
                "mandatory": 1,
                "defaultValue": "0",
                "minimumValue": "0",
                "maximumValue": "2",
                "incrementValue": "2",
            },
            "permanentPressStatus": {
                "category": "command",
                "typology": "range",
                "mandatory": 1,
                "defaultValue": "0",
                "minimumValue": "0",
                "maximumValue": "1",
                "incrementValue": "1",
            },
        },
        "ancillaryParameters": {
            "programType": {"category": "general", "typology": "fixed", "mandatory": 1, "fixedValue": "W"},
            "suggestedLoadW": {"category": "general", "typology": "fixed", "mandatory": 1, "fixedValue": 4},
            "antiWrinkle": {"category": "general", "typology": "fixed", "mandatory": 1, "fixedValue": "1"},
        },
    }
    if include_static_remaining:
        data["remainingTimes"] = {
            "remainingTime": {"category": "time", "typology": "fixed", "mandatory": 1, "fixedValue": "115"}
        }
    return data


def _build_hqd_appliance(
    program_data: Dict[str, Any] | None = None,
    model_attributes: List[Dict[str, Any]] | None = None,
    options: Dict[str, Any] | None = None,
) -> HonAppliance:
    appliance = HonAppliance(None, {"applianceTypeName": "WM", "applianceModelId": 962})
    appliance._appliance_model = {
        "id": 962,
        "attributes": model_attributes if model_attributes is not None else _wm_hqd_model_attributes(),
        "options": options if options is not None else {},
    }
    cmd_data = program_data if program_data is not None else _make_dark_program_data()
    categories: Dict[str, HonCommand] = {}
    cmd = HonCommand(
        "startProgram",
        cmd_data,
        appliance,
        categories=categories,
        category_name="PROGRAMS.WM_WD.IOT_WASH_DARK",
    )
    categories["iot_wash_dark"] = cmd
    appliance._commands["startProgram"] = cmd
    return appliance


def test_hqd_duration_matches_hon_for_defaults_and_option_changes() -> None:
    appliance = _build_hqd_appliance()
    assert is_hqd_duration_supported(appliance) is True

    # Defaults: 30°C, 800 rpm, 10 min main wash, 2 rinses -> 0 + 30 + 23 + 5 + 1 = 59
    assert appliance.settings["startProgram.remainingTime"].value == "59"

    # Raise temp to 40°C -> +10 min = 69
    appliance.settings["startProgram.temp"].value = "40"
    assert appliance.settings["startProgram.remainingTime"].value == "69"

    # Raise temp to 60°C and mainWashTime to 15 -> 0 + 60 + 23 + 5 + 1 = 89
    appliance.settings["startProgram.temp"].value = "60"
    appliance.settings["startProgram.mainWashTime"].value = 15
    assert appliance.settings["startProgram.remainingTime"].value == "89"

    # Enable prewash (haier_SoakPrewashSelection=2) -> +(3 + 17) = +20 -> 109
    appliance.settings["startProgram.haier_SoakPrewashSelection"].value = 2
    assert appliance.settings["startProgram.remainingTime"].value == "109"

    # Disable spin (spinSpeed=0): finalSpinDuration=0 -> prewash 17, mainWash 57, rinse 20, finalSpin 0, antiWrinkle 1 = 95
    appliance.settings["startProgram.spinSpeed"].value = "0"
    assert appliance.settings["startProgram.remainingTime"].value == "95"

    # High spin (1200 rpm) uses pipe-delimited 1200|1400 rinse branch (+7 instead of +5 -> 25)
    appliance.settings["startProgram.spinSpeed"].value = "1200"
    assert appliance.settings["startProgram.remainingTime"].value == "111"


def test_permanent_press_override_does_not_mutate_command_parameters() -> None:
    appliance = _build_hqd_appliance()
    appliance.settings["startProgram.permanentPressStatus"].value = 1

    # permanentPressStatus is forced to "0" during calculation, but outgoing payload keeps "1"
    assert appliance.settings["startProgram.remainingTime"].value == "59"
    outgoing = appliance.commands["startProgram"].parameter_groups["parameters"]
    assert outgoing["permanentPressStatus"] == "1"
    assert "remainingTime" not in outgoing


def test_suggested_load_relative_code_and_rounding() -> None:
    data = _make_dark_program_data()
    data["ancillaryParameters"]["suggestedLoadW"]["fixedValue"] = "RL50"
    appliance = _build_hqd_appliance(program_data=data)
    # RL50 of 8 kg = 4 kg -> same 59 min result
    assert appliance.settings["startProgram.remainingTime"].value == "59"

    data["ancillaryParameters"]["suggestedLoadW"]["fixedValue"] = "RL100"
    appliance2 = _build_hqd_appliance(program_data=data)
    appliance2.settings["startProgram.temp"].value = "40"
    # RL100 of 8 kg = 8 kg at 40°C -> mainWash 10+3+37=50, rinse 23, spin 5, antiWrinkle 1 -> 79
    assert appliance2.settings["startProgram.remainingTime"].value == "79"


def test_available_settings_includes_remaining_time_without_static_block() -> None:
    appliance = _build_hqd_appliance(
        program_data=_make_dark_program_data(include_static_remaining=False)
    )
    assert "startProgram.remainingTime" in appliance.available_settings
    assert appliance.settings["startProgram.remainingTime"].value == "59"


def test_option_aliases_and_decimal_comma_and_remaining_time_precedence() -> None:
    attrs = [
        {"parName": "platform", "parValue": "HQD"},
        {"parName": "remainingTime", "parValue": "10"},
        {"parName": "remainingTime2", "parValue": '{"temp":{"30":"baseTime+opt1*1,5","default":"20"}}'},
        {"parName": "baseTime", "parValue": "40"},
    ]
    appliance = _build_hqd_appliance(
        model_attributes=attrs,
        options={"opt1": "haier_SoakPrewashSelection"},
    )
    appliance.settings["startProgram.haier_SoakPrewashSelection"].value = 2
    # remainingTime2 overrides remainingTime; temp=30 -> 40 + 2 * 1.5 = 43
    assert appliance.settings["startProgram.remainingTime"].value == "43"


def test_non_hqd_falls_back_to_static_remaining_time() -> None:
    appliance = _build_hqd_appliance(
        model_attributes=[{"parName": "platform", "parValue": "CANDY"}]
    )
    assert is_hqd_duration_supported(appliance) is False
    assert calculate_hqd_duration(appliance) is None
    assert appliance.settings["startProgram.remainingTime"].value == "115"


def test_unsafe_or_invalid_formula_is_rejected_safely() -> None:
    attrs = [
        {"parName": "platform", "parValue": "HQD"},
        {"parName": "remainingTime", "parValue": "__import__('os').system('echo pwned')"},
    ]
    appliance = _build_hqd_appliance(model_attributes=attrs)
    assert calculate_hqd_duration(appliance) is None
    # Falls back to static remainingTimes.remainingTime
    assert appliance.settings["startProgram.remainingTime"].value == "115"


def test_normalize_model_attributes_handles_dict_and_list() -> None:
    assert normalize_model_attributes({"attributes": {"platform": "HQD"}}) == {
        "platform": "HQD"
    }
    assert normalize_model_attributes(
        {"attributes": [{"parName": "platform", "parValue": "HQD"}, {"bad": 1}]}
    ) == {"platform": "HQD"}
    assert normalize_model_attributes({}) == {}
