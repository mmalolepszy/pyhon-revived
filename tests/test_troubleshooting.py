"""Tests for pyhon.troubleshooting (pure functions, no network)."""

from pyhon.troubleshooting import (
    HonError,
    code_from_title,
    decode_errors,
    error_bits,
    translate,
)

# Excerpt of GET /config/v1/troubleshooting/list?applianceType=WM&brand=haier
ENTRIES = [
    {
        "errorCode": "8000000000000",
        "title": "TROUBLESHOOTING:HAIER:WM.959.E4:TITLE",
        "steps": [
            {"title": "TROUBLESHOOTING:HAIER:WM.959.E4:STEP_01:DESCRIPTION"},
            {"title": "TROUBLESHOOTING:HAIER:WM.959.E4:STEP_02:DESCRIPTION"},
        ],
    },
    {
        "errorCode": "100000000000",
        "title": "TROUBLESHOOTING:HAIER:WM.959.E2:TITLE",
        "steps": [],
    },
    {
        "errorCode": "400000000000000",
        "title": "TROUBLESHOOTING:HAIER:WM.959.UNB:TITLE",
    },
    {
        "errorCode": "03",
        "platform": "chg",
        "userErrorCode": "E03",
        "title": "TROUBLESHOOTING:CANDY:WM.GENERAL.E03:TITLE",
    },
]


def test_no_error_values() -> None:
    for raw in ("", "0", "00", None, 0):
        assert decode_errors(raw, ENTRIES) == []


def test_single_bit_is_resolved() -> None:
    errors = decode_errors("8000000000000", ENTRIES)
    assert [error.code for error in errors] == ["E4"]
    assert errors[0].raw == "8000000000000"
    assert errors[0].title_key == "TROUBLESHOOTING:HAIER:WM.959.E4:TITLE"
    assert len(errors[0].steps) == 2
    assert str(errors[0]) == "E4"


def test_multiple_bits_are_all_reported() -> None:
    errors = decode_errors("8100000000000", ENTRIES)
    assert [error.code for error in errors] == ["E2", "E4"]


def test_unknown_bit_falls_back_to_bit_number() -> None:
    errors = decode_errors("8000000000000", [])
    assert [error.code for error in errors] == ["bit51"]
    assert errors[0].title_key == ""


def test_candy_platform_code_is_matched_as_a_whole() -> None:
    assert [error.code for error in decode_errors("03", ENTRIES)] == ["E03"]
    assert [error.code for error in decode_errors("3", ENTRIES)] == ["E03"]


def test_garbage_is_returned_verbatim() -> None:
    errors = decode_errors("xyz", ENTRIES)
    assert errors == [HonError(code="xyz", raw="xyz")]


def test_error_bits() -> None:
    assert error_bits("8100000000000") == ["100000000000", "8000000000000"]
    assert not error_bits("00")
    assert not error_bits("nope")


def test_code_from_title() -> None:
    assert code_from_title("TROUBLESHOOTING:HAIER:WM.959.E4A:TITLE") == "E4A"
    assert code_from_title("TROUBLESHOOTING:GENERAL:WM.GENERAL.E61:TITLE") == "E61"
    assert code_from_title("no title key") == ""


def test_translate_nested_keys() -> None:
    translations = {
        "TROUBLESHOOTING:HAIER:WM": {"959": {"E4:TITLE": "E4 - Water inlet error"}}
    }
    key = "TROUBLESHOOTING:HAIER:WM.959.E4:TITLE"
    assert translate(translations, key) == "E4 - Water inlet error"
    assert translate(translations, "TROUBLESHOOTING:HAIER:WM.959.E5:TITLE") == ""
    assert translate({}, key) == ""
