from pyhon.helper import str_to_float


def test_str_to_float_keeps_fraction_of_float() -> None:
    assert str_to_float(7.5) == 7.5
    assert str_to_float(7.8) == 7.8


def test_str_to_float_whole_numbers_stay_int() -> None:
    assert isinstance(str_to_float(8.0), int)
    assert str_to_float(8.0) == 8
    assert isinstance(str_to_float("8"), int)


def test_str_to_float_parses_strings() -> None:
    assert str_to_float("7.5") == 7.5
    assert str_to_float("7,5") == 7.5
