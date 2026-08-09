"""Shared fixtures for loading real hOn appliance test data.

The `tests/hon-test-data` submodule contains anonymized JSON exports
contributed by the community (see https://github.com/mmalolepszy/hon-test-data).
Each directory under `test_data/` is one appliance (e.g. `ac_311`,
`ov_577`, `wm_1569`) and contains the same JSON payloads the real hOn
API returns:

    appliance_data.json   -> appliance info (model, brand, code, ...)
    commands.json         -> full commands map (load_commands)
    attributes.json       -> live attributes (load_attributes)
    command_history.json  -> recent commands (load_command_history)
    statistics.json       -> usage statistics
    maintenance.json      -> maintenance data

These fixtures let us instantiate HonAppliance with real data without
needing credentials, so a regression that breaks parsing for a specific
appliance model is caught by CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

TEST_DATA_ROOT = Path(__file__).parent / "hon-test-data" / "test_data"


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        # Some entries in hon-test-data have malformed JSON (e.g. td_144).
        # Skip them with a clear marker so the test reports them explicitly.
        return {"__json_error__": str(exc), "__path__": str(path)}


def list_available_appliances() -> list[str]:
    """Return all appliance directory names available in the submodule."""
    if not TEST_DATA_ROOT.is_dir():
        return []
    return sorted(p.name for p in TEST_DATA_ROOT.iterdir() if p.is_dir())


def build_appliance_data(appliance_id: str) -> Dict[str, Any]:
    """Load the four main JSON files for one appliance."""
    base = TEST_DATA_ROOT / appliance_id
    return {
        "appliance_data": _load_json(base / "appliance_data.json", {}),
        "commands": _load_json(base / "commands.json", {}),
        "attributes": _load_json(base / "attributes.json", {}),
        "command_history": _load_json(base / "command_history.json", []),
        "statistics": _load_json(base / "statistics.json", {}),
        "maintenance": _load_json(base / "maintenance.json", {}),
    }


def make_mock_api(appliance_id: str) -> AsyncMock:
    """Return an AsyncMock mimicking HonAPI for one appliance directory."""
    data = build_appliance_data(appliance_id)
    mock = AsyncMock()
    mock.load_commands.return_value = dict(data["commands"])
    mock.load_favourites.return_value = []
    mock.load_command_history.return_value = data["command_history"]
    mock.load_attributes.return_value = dict(data["attributes"])
    mock.load_statistics.return_value = dict(data["statistics"])
    mock.load_maintenance.return_value = dict(data["maintenance"])
    return mock


@pytest.fixture(params=list_available_appliances(), ids=lambda x: x)
def appliance_id(request) -> str:
    """Parametrized fixture yielding every appliance id in test_data."""
    return request.param


def pytest_collection_modifyitems(items):
    """Skip appliances whose appliance_data.json is malformed upstream."""
    for item in items:
        # The appliance_id is the last part of the test id, e.g.
        # tests/test_integration.py::test_xxx[ac_311] -> ac_311
        if "[" not in item.name:
            continue
        appliance_id = item.name.rsplit("[", 1)[1].rstrip("]")
        data = build_appliance_data(appliance_id)
        if "__json_error__" in data.get("appliance_data", {}):
            item.add_marker(
                pytest.mark.skip(
                    reason=f"malformed JSON in {data['appliance_data']['__path__']}"
                )
            )
