"""The connection flag follows the cloud record (REST) and the MQTT presence messages."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any, Dict, List

from pyhon.appliance import HonAppliance
from pyhon.connection.mqtt import MQTTClient

TOPICS = [
    "haier/things/x/connected",
    "haier/things/x/disconnected",
    "haier/things/x/appliancestatus",
]


class FakeAPI:
    def __init__(self, category: str) -> None:
        self.category = category

    async def load_attributes(self, appliance: Any) -> Dict[str, Any]:
        return {
            "shadow": {"parameters": {}},
            "lastConnEvent": {"category": self.category},
        }


def make_appliance(category: str) -> HonAppliance:
    appliance = HonAppliance(
        FakeAPI(category),  # type: ignore[arg-type]
        {"applianceTypeName": "WM", "nickName": "Washer", "topics": {"subscribe": TOPICS}},
    )
    asyncio.run(appliance.load_attributes())
    return appliance


def message(topic: str, payload: Dict[str, Any]) -> Any:
    return SimpleNamespace(
        publish_packet=SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())
    )


def test_connection_follows_the_rest_record() -> None:
    assert make_appliance("DISCONNECTED").connection is False
    assert make_appliance("CONNECTED").connection is True


def test_mqtt_presence_updates_flag_and_record() -> None:
    appliance = make_appliance("CONNECTED")
    notified: List[bool] = []
    hon = SimpleNamespace(api=None, appliances=[appliance], notify=lambda: notified.append(True))
    client = MQTTClient(hon, "mobile")  # type: ignore[arg-type]

    client._on_publish_received(message(TOPICS[1], {"disconnectReason": "standby"}))
    assert appliance.connection is False
    assert appliance.attributes["lastConnEvent"]["category"] == "DISCONNECTED"

    client._on_publish_received(message(TOPICS[0], {}))
    assert appliance.connection is True
    assert appliance.attributes["lastConnEvent"]["category"] == "CONNECTED"
    assert len(notified) == 2
