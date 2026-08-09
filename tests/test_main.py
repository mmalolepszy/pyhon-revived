"""Tests for pyhon.__main__ CLI argument parsing.

Covers the fix for Python 3.14 compatibility where positional arguments
with action="store_true" raise ValueError.
"""

import sys
from unittest.mock import patch

import pytest

from pyhon.__main__ import get_arguments


class TestGetArguments:
    """Test CLI argument parsing for all subcommands."""

    def test_export_subcommand(self):
        with patch.object(sys, "argv", ["pyhon", "export", "--anonymous", "/tmp/data"]):
            args = get_arguments()
            assert args["command"] == "export"
            assert args["anonymous"] is True
            assert args["directory"] == "/tmp/data"
            assert args["zip"] is False

    def test_export_with_zip(self):
        with patch.object(sys, "argv", ["pyhon", "export", "--zip"]):
            args = get_arguments()
            assert args["command"] == "export"
            assert args["zip"] is True
            assert args["anonymous"] is False

    def test_export_default_directory(self):
        with patch.object(sys, "argv", ["pyhon", "export"]):
            args = get_arguments()
            assert args["command"] == "export"
            assert args["directory"] is not None  # defaults to cwd

    def test_keys_subcommand(self):
        with patch.object(sys, "argv", ["pyhon", "keys", "--all"]):
            args = get_arguments()
            assert args["command"] == "keys"
            assert args["all"] is True

    def test_keys_default(self):
        with patch.object(sys, "argv", ["pyhon", "keys"]):
            args = get_arguments()
            assert args["command"] == "keys"
            assert args["all"] is False

    def test_translate_subcommand(self):
        with patch.object(sys, "argv", ["pyhon", "translate", "en"]):
            args = get_arguments()
            assert args["translate"] == "en"
            assert args["json"] is False
            # translate has no command set_defaults, so command key is absent
            assert "command" not in args

    def test_translate_with_json(self):
        with patch.object(sys, "argv", ["pyhon", "translate", "de", "--json"]):
            args = get_arguments()
            assert args["translate"] == "de"
            assert args["json"] is True

    def test_no_subcommand(self):
        with patch.object(sys, "argv", ["pyhon"]):
            args = get_arguments()
            # no subcommand -> neither command nor translate keys exist
            assert "command" not in args
            assert "translate" not in args

    def test_user_password_flags(self):
        with patch.object(sys, "argv", ["pyhon", "-u", "test@example.com", "-p", "secret"]):
            args = get_arguments()
            assert args["user"] == "test@example.com"
            assert args["password"] == "secret"

    def test_output_flag(self):
        with patch.object(sys, "argv", ["pyhon", "-o", "/tmp/output.txt"]):
            args = get_arguments()
            assert args["output"] == "/tmp/output.txt"

    def test_import_flag(self):
        with patch.object(sys, "argv", ["pyhon", "-i", "/tmp/import"]):
            args = get_arguments()
            assert args["import"] == "/tmp/import"
