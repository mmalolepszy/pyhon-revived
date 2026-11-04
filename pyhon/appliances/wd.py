# pylint: disable=duplicate-code
from typing import Dict, Any

from pyhon.appliances.base import ApplianceBase


class Appliance(ApplianceBase):
    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return super().laundry_attributes(data)

    def settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return settings
