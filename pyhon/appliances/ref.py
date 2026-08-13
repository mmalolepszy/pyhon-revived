from typing import Dict, Any

from pyhon.appliances.base import ApplianceBase


class Appliance(ApplianceBase):
    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = super().attributes(data)
        if self._param_value(data, "holidayMode") == 1:
            data["modeZ1"] = "holiday"
        elif self._param_value(data, "intelligenceMode") == 1:
            data["modeZ1"] = "auto_set"
        elif self._param_value(data, "quickModeZ1") == 1:
            data["modeZ1"] = "super_cool"
        else:
            data["modeZ1"] = "no_mode"

        if self._param_value(data, "quickModeZ2") == 1:
            data["modeZ2"] = "super_freeze"
        elif self._param_value(data, "intelligenceMode") == 1:
            data["modeZ2"] = "auto_set"
        else:
            data["modeZ2"] = "no_mode"

        return data
