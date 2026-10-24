"""The compact 5-byte frame for the incubator / poultry-house sensor node.

    byte 0   bits 7..6  format version (this is version 1)
             bit  5     door open (1) / shut (0)
             bits 4..0  alarm code 0..31 (0 = none)
    byte 1-2 temperature, int16 big-endian, 0.01 degC      (-327.68 .. 327.67)
    byte 3   relative humidity, uint8, 0.5 %                (0 .. 127.5, clamp to 100)
    byte 4   battery, uint8, 10 mV steps above 2.00 V       (2.00 .. 4.55 V)

Rounding is half away from zero on the exact decimal (rounding.py), so the C encoder, which
only has integers, produces the same bytes.

Why these choices: the SHT31 resolves 0.01 degC, so temperature keeps two decimals; humidity
at 0.5 % matches the sensor's accuracy (+-2 %) and CayenneLPP's own humidity step; a 2.0-4.55 V
span covers a Li-ion cell, a LiFePO4 cell and 2xAA.  The version bits let a decoder reject
frames from older firmware instead of misreading them.  The same layout is in
lib/payload_codec/compact_codec.c (C) and decoder/decoder.js (JavaScript).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .rounding import steps

VERSION = 1
SIZE = 5
TEMP_SCALE = 0.01
HUM_SCALE = 0.5
BATT_OFFSET_MV = 2000
BATT_STEP_MV = 10


@dataclass(frozen=True)
class Reading:
    temperature_c: float
    humidity_pct: float
    battery_v: float
    door_open: bool
    alarm_code: int = 0

    def as_dict(self) -> dict[str, float | bool | int]:
        return asdict(self)


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def encode(r: Reading) -> bytes:
    _check(0 <= r.alarm_code <= 31, f"alarm_code {r.alarm_code} must be 0..31")
    temp_raw = steps(r.temperature_c, TEMP_SCALE)
    _check(-32768 <= temp_raw <= 32767, f"temperature {r.temperature_c} out of int16 range")
    _check(0 <= r.humidity_pct <= 100, f"humidity {r.humidity_pct} must be 0..100 %")
    batt_mv = steps(r.battery_v, 0.001)
    _check(
        BATT_OFFSET_MV <= batt_mv <= BATT_OFFSET_MV + 255 * BATT_STEP_MV,
        f"battery {r.battery_v} V must be 2.00..4.55 V",
    )
    flags = (VERSION << 6) | (0x20 if r.door_open else 0) | r.alarm_code
    hum_raw = steps(r.humidity_pct, HUM_SCALE)
    batt_raw = steps(batt_mv - BATT_OFFSET_MV, BATT_STEP_MV)
    return bytes((flags,)) + temp_raw.to_bytes(2, "big", signed=True) + bytes((hum_raw, batt_raw))


def decode(payload: bytes) -> Reading:
    _check(len(payload) == SIZE, f"compact frame is {SIZE} bytes, got {len(payload)}")
    version = payload[0] >> 6
    _check(version == VERSION, f"unsupported compact frame version {version}")
    temp_raw = int.from_bytes(payload[1:3], "big", signed=True)
    return Reading(
        temperature_c=temp_raw / 100,
        humidity_pct=payload[3] * HUM_SCALE,
        battery_v=(BATT_OFFSET_MV + payload[4] * BATT_STEP_MV) / 1000,
        door_open=bool(payload[0] & 0x20),
        alarm_code=payload[0] & 0x1F,
    )


def quantise(r: Reading) -> Reading:
    """The reading as the receiver will see it after one encode/decode (the loss is the
    0.5 % humidity step and the 10 mV battery step; temperature is exact to 0.01 degC)."""
    return decode(encode(r))
