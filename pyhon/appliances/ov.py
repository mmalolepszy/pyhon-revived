from typing import Any, Dict

from pyhon.appliances.base import ApplianceBase


class Appliance(ApplianceBase):
    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = super().attributes(data)
        if not self.parent.connection:
            for key in ("temp", "onOffStatus", "remoteCtrValid", "remainingTimeMM"):
                if (param := data.get("parameters", {}).get(key)) is not None:
                    param.value = "0"

        data["active"] = self._param_value(data, "onOffStatus") == 1
        return data
