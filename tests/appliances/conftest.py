from types import SimpleNamespace
from typing import Any, Callable

import pytest

from pyhon.attributes import HonAttribute

AttributesFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def attributes() -> AttributesFactory:
    """Run Appliance.attributes() for a machMode, without a real HonAppliance."""

    def _attributes(
        appliance_class: type, mach_mode: str, connection: bool = True
    ) -> dict[str, Any]:
        parent = SimpleNamespace(connection=connection, settings={})
        appliance = appliance_class(parent)
        data = {"parameters": {"machMode": HonAttribute(mach_mode)}}
        result: dict[str, Any] = appliance.attributes(data)
        return result

    return _attributes
