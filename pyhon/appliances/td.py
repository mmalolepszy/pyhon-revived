# pylint: disable=duplicate-code
from typing import Any, Dict

from pyhon.appliances.base import ApplianceBase
from pyhon.parameter.fixed import HonParameterFixed


class Appliance(ApplianceBase):
    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return super().laundry_attributes(data)

    def settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        dry_level = settings.get("startProgram.dryLevel")
        if isinstance(dry_level, HonParameterFixed) and dry_level.value == "11":
            settings.pop("startProgram.dryLevel", None)
        return settings
