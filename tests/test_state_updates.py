"""Regression tests for stale laundry state; no account or network is used."""

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from pyhon.appliance import HonAppliance
from pyhon.attributes import HonAttribute
from pyhon.connection.mqtt import MQTTClient
from pyhon.hon import Hon


async def appliance(kind="TD"):
    device = await HonAppliance(
        None,
        {
            "applianceTypeName": kind,
            "topics": {
                "subscribe": [
                    "test/appliancestatus",
                    "test/connected",
                    "test/disconnected",
                ]
            },
        },
    ).create()
    device.attributes["parameters"] = {
        "machMode": HonAttribute("1"),
        "doorStatus": HonAttribute("1"),
        "prCode": HonAttribute("0"),
    }
    device.connection = True
    device.refresh_derived_attributes()
    return device


def message(topic, payload):
    return SimpleNamespace(
        publish_packet=SimpleNamespace(
            topic=topic, payload=json.dumps(payload).encode()
        )
    )


def client(device):
    hon = SimpleNamespace(api=Mock(), appliances=[device], notify=Mock())
    mqtt = MQTTClient(hon, "test")
    mqtt._loop = asyncio.get_running_loop()
    return mqtt, hon


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["WM", "TD", "WD"])
async def test_laundry_finish_pause_and_door_from_push(kind):
    device = await appliance(kind)
    mqtt, hon = client(device)
    device.attributes["activity"] = {"stale": "previous REST cycle"}
    for mode, active, paused in [
        (2, True, False),
        (3, True, True),
        (7, False, False),
        (1, False, False),
    ]:
        mqtt._process_publish(
            message(
                "test/appliancestatus",
                {
                    "parameters": [
                        {"parName": "machMode", "parNewVal": str(mode)},
                        {"parName": "doorStatus", "parNewVal": "0"},
                    ]
                },
            )
        )
        assert device.get("active") is active
        assert device.get("pause") is paused
        assert device.get("doorStatus") == 0
    assert hon.notify.call_count == 4


@pytest.mark.asyncio
async def test_connection_snapshot_and_live_flag_agree():
    device = await appliance()
    mqtt, _ = client(device)
    for connected in (False, True):
        mqtt._process_publish(
            message("test/connected" if connected else "test/disconnected", {})
        )
        assert device.connection is connected
        assert device.get("attributes.lastConnEvent.category") == (
            "CONNECTED" if connected else "DISCONNECTED"
        )


@pytest.mark.asyncio
async def test_callbacks_are_on_event_loop_and_late_callbacks_ignored():
    device = await appliance()
    mqtt, hon = client(device)
    observed = []
    hon.notify.side_effect = lambda: observed.append(threading.get_ident())
    event = message("test/disconnected", {})
    await asyncio.to_thread(mqtt._on_publish_received, event)
    await asyncio.sleep(0)
    assert observed == [threading.get_ident()]
    await mqtt.close()
    mqtt._on_publish_received(message("test/connected", {}))
    await asyncio.sleep(0)
    assert device.connection is False


@pytest.mark.asyncio
async def test_bad_messages_do_not_break_next_valid_message():
    device = await appliance()
    mqtt, _ = client(device)
    bad = message("test/appliancestatus", {})
    bad.publish_packet.payload = b"not json"
    mqtt._process_publish(bad)
    for topic, payload in [
        ("other/topic", {}),
        ("test/appliancestatus", []),
        ("test/appliancestatus", {"parameters": None}),
        (
            "test/appliancestatus",
            {"parameters": [None, {"parName": "newParameter", "parNewVal": "7"}]},
        ),
    ]:
        mqtt._process_publish(message(topic, payload))
    mqtt._process_publish(
        message(
            "test/appliancestatus",
            {"parameters": [{"parName": "doorStatus", "parNewVal": "0"}]},
        )
    )
    assert device.get("doorStatus") == 0
    assert device.get("newParameter") == 7


@pytest.mark.asyncio
async def test_rest_snapshot_recovers_missed_door_and_connection():
    device = await appliance()
    device.connection = False
    device._api = SimpleNamespace(
        load_attributes=AsyncMock(
            return_value={
                "lastConnEvent": {"category": "CONNECTED"},
                "shadow": {
                    "parameters": {
                        "doorStatus": {"parNewVal": "0"},
                        "machMode": {"parNewVal": "7"},
                    }
                },
            }
        )
    )
    await device.update(force=True)
    assert device.connection is True
    assert device.get("doorStatus") == 0
    assert device.get("active") is False


@pytest.mark.asyncio
async def test_newer_push_wins_over_inflight_rest_snapshot():
    device = await appliance()
    mqtt, _ = client(device)

    async def snapshot(_device):
        mqtt._process_publish(message("test/disconnected", {}))
        return {"lastConnEvent": {"category": "CONNECTED"}}

    device._api = SimpleNamespace(load_attributes=snapshot)
    await device.load_attributes()
    assert device.connection is False
    assert device.get("attributes.lastConnEvent.category") == "DISCONNECTED"


@pytest.mark.asyncio
async def test_close_cancels_watchdog_and_stops_mqtt():
    device = await appliance()
    mqtt, _ = client(device)
    transport = Mock()
    mqtt._client = transport
    task = asyncio.create_task(asyncio.sleep(999))
    mqtt._watchdog_task = task
    await mqtt.close()
    await mqtt.close()
    assert task.cancelled()
    transport.stop.assert_called_once()
    hon = Hon()
    hon._mqtt_client = SimpleNamespace(close=AsyncMock())
    hon._api = SimpleNamespace(close=AsyncMock())
    close_mqtt, close_api = hon._mqtt_client.close, hon._api.close
    await hon.close()
    close_mqtt.assert_awaited_once()
    close_api.assert_awaited_once()
