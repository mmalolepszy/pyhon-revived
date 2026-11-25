import json
from pathlib import Path
from typing import Any

import pytest

from pyhon.appliance import HonAppliance
from pyhon.connection.api import TestAPI as FakeAPI
from pyhon.connection.mqtt import MQTTClient

TOPIC = "haier/things/aa-bb-cc-dd-ee-ff/event/appliancestatus/update"
DISCONNECTED = "$aws/events/presence/disconnected/aa-bb-cc-dd-ee-ff"
OTHER = "haier/things/11-22-33-44-55-66/event/appliancestatus/update"
INFO = {
    "applianceTypeName": "WC",
    "applianceModelId": 1,
    "nickName": "Wine cellar",
    "macAddress": "aa-bb-cc-dd-ee-ff",
    "zone": "2",
    "topics": {"subscribe": [TOPIC, DISCONNECTED]},
}


class FakeHon:
    def __init__(self, appliances: list[HonAppliance]) -> None:
        self.appliances = appliances
        self.notified = 0

    def notify(self) -> None:
        self.notified += 1


@pytest.fixture(name="hon")
async def fixture_hon(tmp_path: Path) -> FakeHon:
    data = tmp_path / "wc_1"
    data.mkdir()
    (data / "appliance_data.json").write_text(json.dumps(INFO))
    (data / "commands.json").write_text(json.dumps({}))
    parameters = {"tempSel": "16", "tempSelZ2": "8", "lightStatus": "0"}
    attributes = {
        "shadow": {"parameters": {k: {"parNewVal": v} for k, v in parameters.items()}}
    }
    (data / "attributes.json").write_text(json.dumps(attributes))
    appliances = []
    # Same order as Hon.setup: the zone clones first, then the base appliance
    for zone in (1, 2, 0):
        appliance = HonAppliance(FakeAPI(tmp_path), dict(INFO), zone=zone)
        await appliance.load_attributes()
        appliances.append(appliance)
    return FakeHon(appliances)


def client_for(hon: FakeHon) -> MQTTClient:
    # pylint: disable=protected-access
    client = MQTTClient.__new__(MQTTClient)
    client._hon = hon  # type: ignore[assignment]
    client._appliances = hon.appliances
    return client


def handle(client: MQTTClient, topic: str, payload: dict[str, Any]) -> None:
    client._handle_message(topic, payload)  # pylint: disable=protected-access


def value(appliance: HonAppliance, key: str) -> str:
    return str(appliance.attributes["parameters"][key])


async def test_status_update_reaches_every_zone_and_base(hon: FakeHon) -> None:
    client = client_for(hon)
    change = {"parName": "tempSelZ2", "parOldVal": "8", "parNewVal": "10"}
    handle(client, TOPIC, {"parameters": [change]})
    assert [a.zone for a in hon.appliances] == [1, 2, 0]
    assert [value(a, "tempSelZ2") for a in hon.appliances] == ["10", "10", "10"]
    assert hon.notified == 1


async def test_presence_reaches_every_zone_and_base(hon: FakeHon) -> None:
    client = client_for(hon)
    handle(client, DISCONNECTED, {"disconnectReason": "CONNECTION_LOST"})
    assert [a.connection for a in hon.appliances] == [False, False, False]
    assert hon.notified == 1


async def test_unknown_topic_is_ignored(hon: FakeHon) -> None:
    client = client_for(hon)
    change = {"parName": "tempSelZ2", "parOldVal": "8", "parNewVal": "10"}
    handle(client, OTHER, {"parameters": [change]})
    assert [value(a, "tempSelZ2") for a in hon.appliances] == ["8", "8", "8"]
    assert hon.notified == 0
