import sys

import pytest

from pyhon.__main__ import get_arguments


def parse(monkeypatch: pytest.MonkeyPatch, *args: str) -> dict:
    monkeypatch.setattr(sys, "argv", ["pyhon", *args])
    return get_arguments()


def test_no_command(monkeypatch: pytest.MonkeyPatch) -> None:
    args = parse(monkeypatch, "-u", "user", "-p", "pass")
    assert args["user"] == "user"
    assert args["password"] == "pass"
    assert not {"keys", "export", "translate"} & args.keys()


def test_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    args = parse(monkeypatch, "keys", "--all")
    assert args["keys"] is True
    assert args["all"] is True
    assert "export" not in args


def test_export(monkeypatch: pytest.MonkeyPatch) -> None:
    args = parse(monkeypatch, "export", "--zip", "data")
    assert args["export"] is True
    assert args["zip"] is True
    assert args["anonymous"] is False
    assert args["directory"] == "data"
    assert "keys" not in args


def test_translate(monkeypatch: pytest.MonkeyPatch) -> None:
    args = parse(monkeypatch, "translate", "es", "--json")
    assert args["translate"] == "es"
    assert args["json"] is True
