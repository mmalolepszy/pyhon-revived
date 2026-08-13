# pylint: disable=duplicate-code
from typing import Any, Dict

from pyhon.appliances.base import ApplianceBase


class Appliance(ApplianceBase):
    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = super().attributes(data)
        if data.get("lastConnEvent", {}).get("category", "") == "DISCONNECTED":
            if (mach := data.get("parameters", {}).get("machMode")) is not None:
                mach.value = "0"
        data["active"] = bool(data.get("activity"))
        data["pause"] = self._param_value(data, "machMode") == 3
        return data

    def settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return settings
