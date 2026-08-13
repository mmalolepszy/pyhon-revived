"""Integration tests against real hOn appliance exports.

For every directory in `tests/hon-test-data/test_data/<appliance>/` we
build a `HonAppliance` with a mocked API that returns the real JSON
payloads. We then verify that:

1. The appliance loads without raising (covers HonRuleSet crashes,
   HonParameterEnum TypeErrors, attribute unwrapping, etc.).
2. Commands and categories are populated as expected.
3. Attribute access returns unwrapped scalars (not HonAttribute objects).
4. Parameter values can be read without raising.

These tests are parametrized: any new directory added to the
`hon-test-data` submodule is automatically picked up.

To contribute your own appliance data, run:

    pyhOn export --anonymous tests/hon-test-data/test_data/

then commit the new `<type>_<id>/` directory and push the submodule
update. See https://github.com/mmalolepszy/hon-test-data for details.
"""

from __future__ import annotations

import pytest

from pyhon.appliance import HonAppliance
from pyhon.attributes import HonAttribute

from conftest import build_appliance_data, make_mock_api


@pytest.mark.asyncio
async def test_appliance_loads_without_crash(appliance_id: str) -> None:
    """Smoke test: every appliance in test_data must load cleanly."""
    api = make_mock_api(appliance_id)
    info = build_appliance_data(appliance_id)["appliance_data"]

    appliance = HonAppliance(api, info)
    await appliance.create()
    await appliance.load_commands()
    await appliance.load_attributes()

    # The appliance must expose the three main collections
    assert appliance.commands is not None
    assert appliance.attributes is not None
    assert appliance.settings is not None


@pytest.mark.asyncio
async def test_appliance_has_start_program_command(appliance_id: str) -> None:
    """Every appliance must expose at least the startProgram command."""
    api = make_mock_api(appliance_id)
    info = build_appliance_data(appliance_id)["appliance_data"]

    appliance = HonAppliance(api, info)
    await appliance.create()
    await appliance.load_commands()

    assert (
        "startProgram" in appliance.commands
    ), f"{appliance_id}: startProgram command missing"


@pytest.mark.asyncio
async def test_appliance_settings_access_returns_unwrapped(appliance_id: str) -> None:
    """Settings access must return unwrapped values, not HonAttribute."""
    api = make_mock_api(appliance_id)
    info = build_appliance_data(appliance_id)["appliance_data"]

    appliance = HonAppliance(api, info)
    await appliance.create()
    await appliance.load_commands()
    await appliance.load_attributes()

    # Iterate over every setting and check it can be read without raising
    for key, param in appliance.settings.items():
        value = param.value
        assert not isinstance(
            value, HonAttribute
        ), f"{appliance_id}.{key}: value is still a HonAttribute wrapper"


@pytest.mark.asyncio
async def test_appliance_attributes_access_returns_unwrapped(appliance_id: str) -> None:
    """Attribute access must return unwrapped values."""
    api = make_mock_api(appliance_id)
    info = build_appliance_data(appliance_id)["appliance_data"]

    appliance = HonAppliance(api, info)
    await appliance.create()
    await appliance.load_attributes()

    for key in appliance.attributes.get("parameters", {}):
        value = appliance.get(f"attributes.parameters.{key}")
        assert not isinstance(
            value, HonAttribute
        ), f"{appliance_id}.attributes.parameters.{key}: value is still wrapped"
