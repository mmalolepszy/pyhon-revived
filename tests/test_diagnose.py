import json

from pyhon.diagnose import anonymize_mqtt_message

MAC = "1a-2b-3c-4d-5e-6f"


def test_status_message_hides_mac_and_time() -> None:
    topic = f"haier/things/{MAC}/event/appliancestatus/update"
    payload = {
        "macAddress": MAC,
        "timestamp": "2026-11-23T21:51:33.3Z",
        "transactionId": f"{MAC}_2026-11-23T21:51:33.3Z",
        "parameters": [{"parName": "opt5", "parOldVal": "1", "parNewVal": "0"}],
    }
    text = anonymize_mqtt_message(topic, json.dumps(payload))
    assert MAC not in text
    assert "2026-11-23" not in text
    assert '"parName": "opt5"' in text


def test_presence_message_hides_ip_and_session() -> None:
    topic = f"$aws/events/presence/connected/{MAC}"
    payload = {
        "clientId": MAC,
        "eventType": "connected",
        "sessionIdentifier": "5bfc7a76-0459-4f40-bd01-e67fb390c188",
        "principalIdentifier": "9b83c447fca6c2cdb241103ce5092f24",
        "ipAddress": "203.0.113.7",
    }
    text = anonymize_mqtt_message(topic, json.dumps(payload))
    for private in (MAC, "203.0.113.7", "5bfc7a76", "9b83c447"):
        assert private not in text
    assert '"eventType": "connected"' in text
