"""Loggers that write every record twice: unchanged to ``pyhon.*`` and
anonymized to ``pyhon_ha.*`` (safe to share, e.g. via Home Assistant's debug
logging)."""

import hashlib
import logging
import re
import traceback

RAW_ROOT = "pyhon"
HA_ROOT = "pyhon_ha"

_START = r"(?<![0-9A-Za-z])"
_END = r"(?![0-9A-Za-z])"
_MAC = re.compile(_START + r"[0-9A-Fa-f]{2}(?:[-:][0-9A-Fa-f]{2}){5}" + _END)
_UUID = re.compile(
    _START
    + r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
    + _END
)
_ACCOUNT_ID = re.compile(_START + r"001[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?" + _END)
_LONG_HEX = re.compile(_START + r"[0-9A-Fa-f]{32,}" + _END)
_JWT = re.compile(_START + r"eyJ[\w-]+\.[\w-]+\.[\w-]+")
_IP = re.compile(_START + r"(?:\d{1,3}\.){3}\d{1,3}" + _END)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class _Registry:
    """Known private values (names, serial numbers, e-mail) and their replacements."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._pattern: re.Pattern[str] | None = None

    def add(self, value: str, replacement: str) -> None:
        value = value.strip()
        if len(value) < 3 or self._values.get(value) == replacement:
            return
        self._values[value] = replacement
        self._pattern = None

    def apply(self, text: str) -> str:
        if not self._values:
            return text
        if self._pattern is None:
            values = sorted(self._values, key=len, reverse=True)
            self._pattern = re.compile(
                "|".join(rf"(?<!\w){re.escape(v)}(?!\w)" for v in values)
            )
        return self._pattern.sub(lambda m: self._values[m.group(0)], text)


_REGISTRY = _Registry()


def mac_hash(mac: str) -> str:
    """Stable, non-reversible short id of a MAC address."""
    normalized = mac.lower().replace(":", "-")
    return "mac:" + hashlib.sha256(normalized.encode()).hexdigest()[:6]


def register_value(value: str, replacement: str) -> None:
    """Replace every whole-word occurrence of value in anonymized logs."""
    _REGISTRY.add(value, replacement)


def register_appliance(
    appliance_type: str, mac: str, nick_name: str, serial_number: str
) -> None:
    if not _MAC.fullmatch(mac):
        return
    short = mac_hash(mac).removeprefix("mac:")
    register_value(nick_name, f"{appliance_type}-{short}")
    register_value(serial_number, f"<serial:{short}>")


def anonymize(text: str) -> str:
    text = _REGISTRY.apply(text)
    text = _MAC.sub(lambda m: mac_hash(m.group(0)), text)
    text = _UUID.sub("<uuid>", text)
    text = _ACCOUNT_ID.sub("<account>", text)
    text = _JWT.sub("<token>", text)
    text = _LONG_HEX.sub("<id>", text)
    text = _EMAIL.sub("<email>", text)
    return _IP.sub("<ip>", text)


class HonLogger:
    def __init__(self, name: str) -> None:
        self.raw = logging.getLogger(name)
        if name == RAW_ROOT or name.startswith(RAW_ROOT + "."):
            ha_name = HA_ROOT + name[len(RAW_ROOT) :]
        else:
            ha_name = f"{HA_ROOT}.{name}"
        self.ha = logging.getLogger(ha_name)

    def _log(
        self, level: int, msg: object, args: tuple[object, ...], exc: bool
    ) -> None:
        # stacklevel 3: record the caller of debug()/info()/..., not this module
        self.raw.log(level, msg, *args, exc_info=exc, stacklevel=3)
        if not self.ha.isEnabledFor(level):
            return
        text = str(msg) % args if args else str(msg)
        if exc:
            text += "\n" + traceback.format_exc().rstrip()
        self.ha.log(level, "%s", anonymize(text), stacklevel=3)

    def debug(self, msg: object, *args: object) -> None:
        self._log(logging.DEBUG, msg, args, False)

    def info(self, msg: object, *args: object) -> None:
        self._log(logging.INFO, msg, args, False)

    def warning(self, msg: object, *args: object) -> None:
        self._log(logging.WARNING, msg, args, False)

    def error(self, msg: object, *args: object) -> None:
        self._log(logging.ERROR, msg, args, False)

    def exception(self, msg: object, *args: object) -> None:
        self._log(logging.ERROR, msg, args, True)


def get_logger(name: str) -> HonLogger:
    return HonLogger(name)
