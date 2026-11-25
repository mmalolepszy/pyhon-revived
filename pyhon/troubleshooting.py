"""Decode the ``errors`` attribute of hOn appliances into error codes.

The cloud reports appliance errors in the ``errors`` parameter as a
hexadecimal bit field (e.g. ``"8000000000000"`` = bit 51 set, ``"00"`` = no
error). The hOn app resolves it through ``GET /config/v1/troubleshooting/list``
(see :meth:`pyhon.HonAPI.load_troubleshooting`): every entry carries an
``errorCode`` that is either a hex value with exactly one bit set (Haier
platform) or a plain two digit code (Candy platform, ``platform: chg``), and a
``title`` that is a translation key such as
``TROUBLESHOOTING:HAIER:WM.959.E4:TITLE`` whose last segment is the code shown
on the appliance display (``E4``).
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

_NO_ERROR = {"", "0", "00", "none", "null"}
_TITLE_CODE = re.compile(r"\.([A-Za-z0-9_]+):TITLE$")


@dataclass
class HonError:
    """One active appliance error."""

    code: str
    """Code as shown on the appliance display, e.g. ``E4`` (or ``bit51`` when
    the cloud has no entry for the bit)."""
    raw: str
    """Hex value of the single bit (or the plain code for Candy platforms)."""
    title_key: str = ""
    """Translation key of the title (``TROUBLESHOOTING:...:TITLE``)."""
    steps: List[str] = field(default_factory=list)
    """Translation keys of the suggested steps."""

    def __str__(self) -> str:
        return self.code


def code_from_title(title: str) -> str:
    """``TROUBLESHOOTING:HAIER:WM.959.E4:TITLE`` -> ``E4``."""
    if match := _TITLE_CODE.search(title or ""):
        return match.group(1)
    return ""


def error_bits(raw: str) -> List[str]:
    """Split a hex bit field into the hex values of its set bits.

    ``"8100000000000"`` -> ``["100000000000", "8000000000000"]``;
    values that are no hex number (or zero) give an empty list.
    """
    value = str(raw or "").strip().lower()
    if value in _NO_ERROR:
        return []
    try:
        number = int(value, 16)
    except ValueError:
        return []
    bits: List[str] = []
    position = 0
    while number:
        if number & 1:
            bits.append(format(1 << position, "x"))
        number >>= 1
        position += 1
    return bits


def _index(entries: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("errorCode", "")).strip().lower()
        if key and key not in result:
            result[key] = entry
    return result


def _make_error(raw: str, entry: Optional[Dict[str, Any]]) -> HonError:
    if not entry:
        try:
            bit = int(raw, 16).bit_length() - 1
            code = f"bit{bit}"
        except ValueError:
            code = raw
        return HonError(code=code, raw=raw)
    title = str(entry.get("title", ""))
    code = str(entry.get("userErrorCode") or code_from_title(title) or raw)
    steps = [
        str(step.get("title", ""))
        for step in entry.get("steps", []) or []
        if isinstance(step, dict) and step.get("title")
    ]
    return HonError(code=code, raw=raw, title_key=title, steps=steps)


def decode_errors(raw: Any, entries: Iterable[Dict[str, Any]]) -> List[HonError]:
    """Resolve the ``errors`` attribute against the troubleshooting list.

    An exact match of the whole value wins (Candy platform codes like ``"03"``
    are no bit fields); otherwise every set bit of the hex value is looked up
    on its own, so several simultaneous errors are all reported.
    """
    value = str(raw if raw is not None else "").strip().lower()
    if value in _NO_ERROR:
        return []
    index = _index(entries)
    if value in index:
        return [_make_error(value, index[value])]
    if value.isdigit() and value.zfill(2) in index and len(value) <= 2:
        return [_make_error(value.zfill(2), index[value.zfill(2)])]
    bits = error_bits(value)
    if not bits:
        return [HonError(code=value, raw=value)]
    return [_make_error(bit, index.get(bit)) for bit in bits]


def translate(translations: Dict[str, Any], key: str) -> str:
    """Look up a troubleshooting key in the app translations.

    The translation JSON (:meth:`pyhon.HonAPI.translation_keys`) nests the
    dot separated segments of a key:
    ``TROUBLESHOOTING:HAIER:WM.959.E4:TITLE`` is stored under
    ``["TROUBLESHOOTING:HAIER:WM"]["959"]["E4:TITLE"]``.
    Returns an empty string when the key is unknown.
    """
    node: Any = translations
    for segment in key.split("."):
        if not isinstance(node, dict) or segment not in node:
            return ""
        node = node[segment]
    return node if isinstance(node, str) else ""
