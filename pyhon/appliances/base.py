from typing import Dict, Any, TYPE_CHECKING

from pyhon.parameter.program import HonParameterProgram

if TYPE_CHECKING:
    from pyhon.appliance import HonAppliance


class ApplianceBase:
    def __init__(self, appliance: "HonAppliance"):
        self.parent = appliance

    def attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        program_name = "No Program"
        if program := int(str(data.get("parameters", {}).get("prCode", "0"))):
            if start_cmd := self.parent.settings.get("startProgram.program"):
                if isinstance(start_cmd, HonParameterProgram) and (
                    ids := start_cmd.ids
                ):
                    program_name = ids.get(program, program_name)
        data["programName"] = program_name
        return data

    def settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return settings

    def laundry_attributes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Use the current machine mode, not the last REST activity record."""
        data = ApplianceBase.attributes(self, data)
        mode = data.get("parameters", {}).get("machMode")
        mode = getattr(mode, "value", mode)
        try:
            mode = int(mode)
        except (TypeError, ValueError):
            data["active"] = self.parent.connection and bool(data.get("activity"))
            data["pause"] = False
        else:
            data["active"] = self.parent.connection and mode in (2, 3, 4, 5, 9)
            data["pause"] = self.parent.connection and mode == 3
        return data
