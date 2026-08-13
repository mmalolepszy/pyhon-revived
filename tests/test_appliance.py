"""Regression tests for HonAppliance attribute access.

These cover a bug where dotted-path lookups (e.g.
"attributes.parameters.onOffStatus") returned the raw internal
HonAttribute wrapper instead of its unwrapped value, while the
equivalent undotted lookup ("onOffStatus") already unwrapped it. Any
caller comparing the result to a scalar (as Home Assistant's binary
sensors do via `on_value`) silently always mismatched, regardless of
the appliance's real state.
"""

from pyhon.appliance import HonAppliance
from pyhon.attributes import HonAttribute


def make_appliance(zone: int = 0) -> HonAppliance:
    appliance = HonAppliance(
        None,
        {"applianceTypeId": 3, "macAddress": "aa-bb-cc-dd-ee-ff", "zone": "4"},
        zone=zone,
    )
    appliance._attributes = {
        "parameters": {
            "onOffStatusZ1": HonAttribute("1"),
            "onOffStatusZ2": HonAttribute("0"),
            "hotStatusZ1": HonAttribute("1"),
            "powerZ1": HonAttribute("6"),
        },
        "lastConnEvent": {"category": "CONNECTED"},
    }
    return appliance


def test_undotted_parameter_returns_unwrapped_value():
    appliance = make_appliance(zone=1)
    value = appliance.get("onOffStatus")
    assert value == 1
    assert isinstance(value, (int, float))


def test_dotted_parameter_returns_unwrapped_value():
    """Regression test: this used to return a raw HonAttribute object."""
    appliance = make_appliance(zone=1)
    value = appliance.get("attributes.parameters.onOffStatus")
    assert value == 1
    assert isinstance(value, (int, float))
    assert not isinstance(value, HonAttribute)


def test_dotted_and_undotted_parameter_access_agree():
    appliance = make_appliance(zone=1)
    assert appliance.get("onOffStatus") == appliance.get(
        "attributes.parameters.onOffStatus"
    )


def test_zone_suffix_applied_to_dotted_lookup():
    zone1 = make_appliance(zone=1)
    zone2 = make_appliance(zone=2)
    assert zone1.get("attributes.parameters.onOffStatus") == 1
    assert zone2.get("attributes.parameters.onOffStatus") == 0


def test_zone_suffix_applied_to_undotted_lookup():
    zone1 = make_appliance(zone=1)
    zone2 = make_appliance(zone=2)
    assert zone1.get("onOffStatus") == 1
    assert zone2.get("onOffStatus") == 0


def test_missing_dotted_key_returns_default():
    appliance = make_appliance(zone=1)
    assert appliance.get("attributes.parameters.doesNotExist") is None
    assert appliance.get("attributes.parameters.doesNotExist", "fallback") == "fallback"


def test_missing_undotted_key_returns_default():
    appliance = make_appliance(zone=1)
    assert appliance.get("doesNotExist") is None
    assert appliance.get("doesNotExist", "fallback") == "fallback"


def test_dotted_lookup_falls_back_to_unzoned_key_when_not_zone_specific():
    """Not every attribute has a per-zone variant (e.g. connection status
    is device-wide). A zone sub-device must still resolve it via the
    unzoned key instead of raising because "...categoryZ1" doesn't exist.
    """
    appliance = make_appliance(zone=1)
    assert appliance.get("attributes.lastConnEvent.category") == "CONNECTED"


def test_undotted_lookup_falls_back_to_unzoned_key_when_not_zone_specific():
    appliance = make_appliance(zone=1)
    appliance._attributes["sharedFlag"] = "yes"
    assert appliance.get("sharedFlag") == "yes"


def test_zoned_key_still_preferred_over_unzoned_when_both_exist():
    appliance = make_appliance(zone=1)
    appliance._attributes["parameters"]["ambiguousZ1"] = HonAttribute("1")
    appliance._attributes["parameters"]["ambiguous"] = HonAttribute("0")
    assert appliance.get("ambiguous") == 1


def test_bracket_access_matches_get_for_dotted_key():
    appliance = make_appliance(zone=1)
    assert appliance["attributes.parameters.onOffStatus"] == appliance.get(
        "attributes.parameters.onOffStatus"
    )


def test_sync_parameter_with_enum_mismatch_does_not_raise():
    """Regression test for mmalolepszy/hon-revived#40.

    sync_parameter() copies a value from a source parameter to a target
    parameter. When the target is a HonParameterEnum whose allowed values
    (e.g. [2,4,5,6,8]) don't include the source value (e.g. "0"), the
    assignment raised ValueError: "Allowed values: (2,4,5,6,8) But was: 0".

    The sync must be best-effort: an out-of-range value must be skipped
    without crashing the whole command sync.
    """
    from pyhon.parameter.enum import HonParameterEnum
    from pyhon.parameter.base import HonParameter

    source = HonParameter("machMode", {"defaultValue": "0"}, "settings")
    source.value = "0"

    target = HonParameterEnum("machMode", {"enumValues": ["2", "4", "5", "6", "8"]}, "settings")

    appliance = make_appliance()
    appliance.sync_parameter(source, target)  # must not raise


def test_sync_parameter_valid_value_still_synced():
    """A value that IS in the target's allowed list must sync correctly."""
    from pyhon.parameter.enum import HonParameterEnum
    from pyhon.parameter.base import HonParameter

    source = HonParameter("machMode", {"defaultValue": "4"}, "settings")
    source.value = "4"

    target = HonParameterEnum("machMode", {"enumValues": ["2", "4", "5", "6", "8"]}, "settings")

    appliance = make_appliance()
    appliance.sync_parameter(source, target)
    assert target.value == "4"
