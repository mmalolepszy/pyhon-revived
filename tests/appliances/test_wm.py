from typing import Any, Callable

from pyhon.appliances.wm import Appliance

Attributes = Callable[..., dict[str, Any]]


def test_pause_when_mach_mode_is_3(attributes: Attributes) -> None:
    assert attributes(Appliance, "3")["pause"] is True


def test_no_pause_when_running(attributes: Attributes) -> None:
    assert attributes(Appliance, "2")["pause"] is False


def test_no_pause_when_offline(attributes: Attributes) -> None:
    assert attributes(Appliance, "3", connection=False)["pause"] is False
