# pylint: disable=duplicate-code
from typing import Dict, Any

from pyhon.appliances.base import ApplianceBase


class Appliance(ApplianceBase):
    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = super().attributes(data)
        if not self.parent.connection:
            if (mach := data.get("parameters", {}).get("machMode")) is not None:
                mach.value = "0"
        data["active"] = bool(data.get("activity"))
        data["pause"] = self._param_value(data, "machMode") == 3
        return data

    def settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return settings
