"""Tests for HonParameterEnum edge cases."""

from pyhon.parameter.enum import HonParameterEnum


class TestEnumValues:
    """Test enumValues handling for various input types."""

    def test_enum_values_as_list(self):
        param = HonParameterEnum("test", {"enumValues": ["a", "b", "c"]}, "group")
        assert param.values == ["a", "b", "c"]

    def test_enum_values_as_pipe_separated_string(self):
        """Haier sometimes sends enumValues as "2|4|5" instead of list."""
        param = HonParameterEnum("test", {"enumValues": "2|4|5"}, "group")
        assert param.values == ["2", "4", "5"]

    def test_enum_values_as_single_string(self):
        """Single value as plain string should become single-item list."""
        param = HonParameterEnum("test", {"enumValues": "single"}, "group")
        assert param.values == ["single"]

    def test_enum_values_empty(self):
        param = HonParameterEnum("test", {"enumValues": []}, "group")
        assert param.values == []

    def test_enum_values_missing(self):
        param = HonParameterEnum("test", {}, "group")
        assert param.values == []

    def test_enum_values_none(self):
        param = HonParameterEnum("test", {"enumValues": None}, "group")
        assert param.values == []
