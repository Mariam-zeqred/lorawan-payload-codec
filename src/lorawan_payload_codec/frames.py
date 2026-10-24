"""The two uplink formats of the sensor node, told apart by LoRaWAN FPort.

    FPort 1  compact   5 bytes   see compact.py
    FPort 2  CayenneLPP 17 bytes  ch1 temperature, ch2 humidity, ch3 analog_in = battery V,
                                  ch4 digital_in = door (1 open), ch5 digital_in = alarm code

The channel numbers are the contract with the JavaScript decoder and the C encoder
(include/Config.h), so they live here as constants rather than being passed around.
"""

from __future__ import annotations

from . import cayenne, compact
from .compact import Reading

FPORT_COMPACT = 1
FPORT_CAYENNE = 2
CH_TEMPERATURE, CH_HUMIDITY, CH_BATTERY, CH_DOOR, CH_ALARM = 1, 2, 3, 4, 5
FORMATS = ("compact", "cayenne")


def to_cayenne(r: Reading) -> bytes:
    # the same node-level limits as the C encoder, so both refuse the same readings
    if not 0 <= r.humidity_pct <= 100:
        raise ValueError(f"humidity {r.humidity_pct} must be 0..100 %")
    if not 0 <= r.alarm_code <= 31:
        raise ValueError(f"alarm_code {r.alarm_code} must be 0..31")
    lpp = cayenne.CayenneLPP()
    lpp.temperature(CH_TEMPERATURE, r.temperature_c)
    lpp.humidity(CH_HUMIDITY, r.humidity_pct)
    lpp.analog_in(CH_BATTERY, r.battery_v)
    lpp.digital_in(CH_DOOR, int(r.door_open))
    lpp.digital_in(CH_ALARM, r.alarm_code)
    return lpp.bytes


def from_cayenne(payload: bytes) -> Reading:
    d = cayenne.decode(payload)
    try:
        return Reading(
            temperature_c=float(d[f"temperature_{CH_TEMPERATURE}"]),
            humidity_pct=float(d[f"relative_humidity_{CH_HUMIDITY}"]),
            battery_v=float(d[f"analog_in_{CH_BATTERY}"]),
            door_open=bool(d[f"digital_in_{CH_DOOR}"]),
            alarm_code=int(d[f"digital_in_{CH_ALARM}"]),
        )
    except KeyError as e:
        raise ValueError(f"CayenneLPP frame lacks the node's field {e}") from None


def encode(r: Reading, fmt: str) -> tuple[int, bytes]:
    """Return (fport, payload) for the format name."""
    if fmt == "compact":
        return FPORT_COMPACT, compact.encode(r)
    if fmt == "cayenne":
        return FPORT_CAYENNE, to_cayenne(r)
    raise ValueError(f"format must be one of {FORMATS}, got {fmt!r}")


def decode(fport: int, payload: bytes) -> Reading:
    if fport == FPORT_COMPACT:
        return compact.decode(payload)
    if fport == FPORT_CAYENNE:
        return from_cayenne(payload)
    raise ValueError(f"no decoder for FPort {fport}")
