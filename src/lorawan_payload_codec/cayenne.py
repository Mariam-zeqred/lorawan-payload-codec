"""CayenneLPP (Low Power Payload) encoder and decoder.

Each item on the wire is  [channel][type][data...]  with big-endian data.  The type byte fixes
the width, the sign and the scale of the data; the table below is the published CayenneLPP
type list (myDevices "Cayenne LPP" reference, also the type table in The Things Network's
built-in CayenneLPP decoder).  A field is stored as  round(value / scale)  in `size` bytes.

Only the field types in `TYPES` are supported; an unknown type stops decoding with an error
because the width of the data that follows it is unknown.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_PAYLOAD_BYTES = 51  # the EU868 SF12 application-payload limit, the smallest a node must fit


@dataclass(frozen=True)
class Field:
    name: str
    size: int  # bytes per value
    signed: bool
    scale: float  # physical unit per LSB
    unit: str


@dataclass(frozen=True)
class LppType:
    code: int
    name: str
    fields: tuple[Field, ...]

    @property
    def size(self) -> int:
        return sum(f.size for f in self.fields)


def _t(code: int, name: str, *fields: Field) -> LppType:
    return LppType(code, name, fields)


def _f(name: str, size: int, signed: bool, scale: float, unit: str) -> Field:
    return Field(name, size, signed, scale, unit)


TYPES: dict[int, LppType] = {
    t.code: t
    for t in (
        _t(0x00, "digital_in", _f("value", 1, False, 1, "")),
        _t(0x01, "digital_out", _f("value", 1, False, 1, "")),
        _t(0x02, "analog_in", _f("value", 2, True, 0.01, "")),
        _t(0x03, "analog_out", _f("value", 2, True, 0.01, "")),
        _t(0x65, "luminosity", _f("value", 2, False, 1, "lux")),
        _t(0x66, "presence", _f("value", 1, False, 1, "")),
        _t(0x67, "temperature", _f("value", 2, True, 0.1, "degC")),
        _t(0x68, "relative_humidity", _f("value", 1, False, 0.5, "%")),
        _t(
            0x71,
            "accelerometer",
            _f("x", 2, True, 0.001, "g"),
            _f("y", 2, True, 0.001, "g"),
            _f("z", 2, True, 0.001, "g"),
        ),
        _t(0x73, "barometric_pressure", _f("value", 2, False, 0.1, "hPa")),
        _t(
            0x86,
            "gyrometer",
            _f("x", 2, True, 0.01, "deg/s"),
            _f("y", 2, True, 0.01, "deg/s"),
            _f("z", 2, True, 0.01, "deg/s"),
        ),
        _t(
            0x88,
            "gps",
            _f("latitude", 3, True, 0.0001, "deg"),
            _f("longitude", 3, True, 0.0001, "deg"),
            _f("altitude", 3, True, 0.01, "m"),
        ),
    )
}
BY_NAME: dict[str, LppType] = {t.name: t for t in TYPES.values()}


def _quantise(value: float, field: Field) -> int:
    raw = round(value / field.scale)
    bits = 8 * field.size
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if field.signed else (0, (1 << bits) - 1)
    if not lo <= raw <= hi:
        raise ValueError(
            f"{field.name}={value} is outside the CayenneLPP range "
            f"[{lo * field.scale:g}, {hi * field.scale:g}] {field.unit}".rstrip()
        )
    return raw


class CayenneLPP:
    """Build a payload item by item, then read `.bytes` (or `bytes(lpp)`)."""

    def __init__(self, max_bytes: int = MAX_PAYLOAD_BYTES) -> None:
        self.max_bytes = max_bytes
        self._buf = bytearray()

    def add(self, channel: int, type_name: str, *values: float) -> CayenneLPP:
        t = BY_NAME[type_name]
        if not 0 <= channel <= 255:
            raise ValueError("channel must fit in one byte")
        if len(values) != len(t.fields):
            raise ValueError(f"{t.name} takes {len(t.fields)} value(s), got {len(values)}")
        if len(self._buf) + 2 + t.size > self.max_bytes:
            raise ValueError(f"payload would exceed {self.max_bytes} bytes")
        self._buf += bytes((channel, t.code))
        for field, value in zip(t.fields, values, strict=True):
            self._buf += _quantise(value, field).to_bytes(field.size, "big", signed=field.signed)
        return self

    # the five readings this project's sensor node sends, on fixed channels
    def temperature(self, ch: int, deg_c: float) -> CayenneLPP:
        return self.add(ch, "temperature", deg_c)

    def humidity(self, ch: int, percent: float) -> CayenneLPP:
        return self.add(ch, "relative_humidity", percent)

    def analog_in(self, ch: int, value: float) -> CayenneLPP:
        return self.add(ch, "analog_in", value)

    def digital_in(self, ch: int, value: int) -> CayenneLPP:
        return self.add(ch, "digital_in", value)

    @property
    def bytes(self) -> bytes:
        return bytes(self._buf)

    def __bytes__(self) -> bytes:
        return self.bytes

    def __len__(self) -> int:
        return len(self._buf)


def decode(payload: bytes) -> dict[str, float | dict[str, float]]:
    """Decode to `{"<type>_<channel>": value}`, the key style of TTN's built-in decoder.
    Multi-field types (accelerometer, gyrometer, gps) decode to a dict of their fields."""
    out: dict[str, float | dict[str, float]] = {}
    i = 0
    while i < len(payload):
        if i + 2 > len(payload):
            raise ValueError(f"truncated item header at byte {i}")
        channel, code = payload[i], payload[i + 1]
        t = TYPES.get(code)
        if t is None:
            raise ValueError(f"unknown CayenneLPP type 0x{code:02x} at byte {i + 1}")
        i += 2
        if i + t.size > len(payload):
            raise ValueError(f"truncated {t.name} data at byte {i}")
        values: dict[str, float] = {}
        for field in t.fields:
            raw = int.from_bytes(payload[i : i + field.size], "big", signed=field.signed)
            values[field.name] = round(raw * field.scale, 6)
            i += field.size
        key = f"{t.name}_{channel}"
        out[key] = values["value"] if len(t.fields) == 1 else values
    return out
