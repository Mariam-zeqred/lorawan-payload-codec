import pytest

from lorawan_payload_codec import compact
from lorawan_payload_codec.compact import Reading, decode, encode, quantise


def test_layout_of_a_real_reading():
    # first reading of the incubator sample: 26.87 degC, 81.5 %, 3.60 V, door shut, alarm 1
    b = encode(Reading(26.87, 81.5, 3.60, False, 1))
    assert b.hex() == "410a7fa3a0"
    assert b[0] >> 6 == compact.VERSION
    assert int.from_bytes(b[1:3], "big", signed=True) == 2687
    assert b[3] == 163 and b[3] * 0.5 == 81.5
    assert b[4] == 160 and 2000 + 160 * 10 == 3600


def test_flags_byte():
    assert encode(Reading(0, 0, 2.0, True, 31))[0] == 0b01_1_11111
    assert encode(Reading(0, 0, 2.0, False, 0))[0] == 0b01_0_00000
    r = decode(encode(Reading(0, 0, 2.0, True, 31)))
    assert r.door_open is True and r.alarm_code == 31


def test_negative_and_limits_round_trip_exactly():
    for t in (-327.68, -12.34, -0.01, 0.0, 0.01, 327.67):
        assert decode(encode(Reading(t, 50.0, 3.0, False))).temperature_c == t
    assert decode(encode(Reading(0, 0, 2.00, False))).battery_v == 2.00
    assert decode(encode(Reading(0, 100, 4.55, False))).battery_v == 4.55


def test_quantisation_is_the_documented_step():
    q = quantise(Reading(26.874, 67.1, 3.614, False))
    assert q == Reading(26.87, 67.0, 3.61, False, 0)
    assert quantise(Reading(0, 67.3, 3.0, False)).humidity_pct == 67.5


def test_half_steps_round_away_from_zero_like_the_c_encoder():
    assert quantise(Reading(26.855, 60.25, 3.615, False)) == Reading(26.86, 60.5, 3.62, False, 0)
    assert quantise(Reading(-12.345, 0.25, 2.005, False)) == Reading(-12.35, 0.5, 2.01, False, 0)


@pytest.mark.parametrize(
    ("reading", "msg"),
    [
        (Reading(0, 0, 2.0, False, 32), "alarm_code"),
        (Reading(0, 0, 2.0, False, -1), "alarm_code"),
        (Reading(400.0, 0, 2.0, False), "int16"),
        (Reading(0, 100.5, 2.0, False), "humidity"),
        (Reading(0, 0, 1.99, False), "battery"),
        (Reading(0, 0, 4.56, False), "battery"),
    ],
)
def test_encode_rejects_out_of_range(reading, msg):
    with pytest.raises(ValueError, match=msg):
        encode(reading)


def test_decode_rejects_wrong_length_and_version():
    with pytest.raises(ValueError, match="5 bytes"):
        decode(b"\x40\x00\x00\x00")
    with pytest.raises(ValueError, match="version 2"):
        decode(b"\x80\x00\x00\x00\x00")
