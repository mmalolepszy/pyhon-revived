import logging

import pytest

from pyhon import log

MAC = "1c-9d-c2-8a-5d-d4"


def test_mac_becomes_stable_hash() -> None:
    text = log.anonymize(f"haier/things/{MAC}/event - {{'macAddress': '{MAC}'}}")
    assert MAC not in text
    assert text.count(log.mac_hash(MAC)) == 2
    assert log.mac_hash(MAC) == log.mac_hash(MAC.upper().replace("-", ":"))


def test_mac_glued_to_underscore() -> None:
    text = log.anonymize(f"'transactionId': '{MAC}_2026-11-24T10:53:52.4Z'")
    assert text == f"'transactionId': '{log.mac_hash(MAC)}_2026-11-24T10:53:52.4Z'"


def test_different_macs_stay_distinguishable() -> None:
    assert log.mac_hash(MAC) != log.mac_hash("ec-62-60-23-ee-f0")


def test_private_values_masked_and_data_kept() -> None:
    text = log.anonymize(
        "{'sessionIdentifier': '5bfc7a76-0459-4f40-bd01-e67fb390c188', "
        "'principalIdentifier': '9b83c447fca6c2cdb241103ce5092f2412a7eb2f8e6b41551cccab4be1542bfa', "
        "'ipAddress': '203.0.113.7', 'PK': '0015g00000AbCdEFGH', "
        "'token': 'eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM', "
        "'timestamp': '2026-11-23T21:51:33.3Z', 'parName': 'opt5'}"
    )
    for private in ("5bfc7a76", "9b83c447", "203.0.113.7", "0015g00000", "eyJhbGciOi"):
        assert private not in text
    assert "2026-11-23T21:51:33.3Z" in text
    assert "'parName': 'opt5'" in text


def test_writes_raw_and_anonymized(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    log.get_logger("pyhon.test").info("%s - %s", "topic", MAC)
    records = {r.name: r.getMessage() for r in caplog.records}
    assert records == {
        "pyhon.test": f"topic - {MAC}",
        "pyhon_ha.test": f"topic - {log.mac_hash(MAC)}",
    }


def test_anonymized_logger_respects_its_level(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(logging.getLogger("pyhon_ha"), "level", logging.WARNING)
    log.get_logger("pyhon.test").info("debug only %s", MAC)
    assert [r.name for r in caplog.records] == ["pyhon.test"]


def test_exception_traceback_is_anonymized(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    try:
        raise KeyError(MAC)
    except KeyError:
        log.get_logger("pyhon.test").exception("failed")
    raw, ha = caplog.records
    assert raw.exc_info is not None
    assert "KeyError" in ha.getMessage()
    assert MAC not in ha.getMessage()


def test_record_points_to_caller(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    log.get_logger("pyhon.test").warning("here")
    assert {r.funcName for r in caplog.records} == {"test_record_points_to_caller"}


def test_registered_appliance_values_are_replaced() -> None:
    mac = "a1-b2-c3-d4-e5-f6"
    log.register_appliance("AC", mac, "Gabinet", "ABC123456789XYZ")
    short = log.mac_hash(mac).removeprefix("mac:")
    text = log.anonymize("Connected Gabinet, serial ABC123456789XYZ, Gabinety stay")
    assert text == f"Connected AC-{short}, serial <serial:{short}>, Gabinety stay"


def test_masked_test_data_mac_registers_nothing() -> None:
    log.register_appliance("WM", "xx-xx-xx-xx-xx-xx", "Pralka", "XXXX111")
    assert log.anonymize("Connected Pralka") == "Connected Pralka"


def test_email_and_short_values() -> None:
    log.register_value("x1", "<short>")
    text = log.anonymize("user jan.kowalski@example.com, value x1")
    assert text == "user <email>, value x1"
