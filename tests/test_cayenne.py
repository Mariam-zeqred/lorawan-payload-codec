"""CayenneLPP against the byte examples in the public reference: a temperature of 27.2 degC on
channel 3 is `03 67 01 10`, and -4.1 degC on channel 5 is `05 67 FF D7`."""

import pytest

from lorawan_payload_codec import cayenne
from lorawan_payload_codec.cayenne import CayenneLPP, decode


def test_reference_temperature_bytes():
    assert CayenneLPP().temperature(3, 27.2).bytes.hex() == "03670110"
    assert CayenneLPP().temperature(5, -4.1).bytes.hex() == "0567ffd7"
    assert decode(bytes.fromhex("0367011005 67ffd7".replace(" ", ""))) == {
        "temperature_3": 27.2,
        "temperature_5": -4.1,
    }


def test_humidity_half_percent_and_analog_centivolt():
    lpp = CayenneLPP().humidity(2, 81.5).analog_in(3, 3.6)
    assert lpp.bytes.hex() == "0268a3" + "030201" + "68"
    assert decode(lpp.bytes) == {"relative_humidity_2": 81.5, "analog_in_3": 3.6}


def test_every_type_round_trips():
    lpp = CayenneLPP(max_bytes=222)  # the SF7 limit; all twelve types need 59 bytes
    sample = {
        "digital_in": (1,),
        "digital_out": (0,),
        "analog_in": (-12.34,),
        "analog_out": (327.67,),
        "luminosity": (65535,),
        "presence": (1,),
        "temperature": (-40.0,),
        "relative_humidity": (100.0,),
        "accelerometer": (-1.0, 0.5, 2.047),
        "barometric_pressure": (1013.2,),
        "gyrometer": (0.0, -100.5, 327.67),
        "gps": (31.0409, 31.3785, 12.5),  # Mansoura
    }
    for ch, (name, values) in enumerate(sample.items()):
        lpp.add(ch, name, *values)
    out = decode(lpp.bytes)
    assert out["temperature_6"] == -40.0
    assert out["accelerometer_8"] == {"x": -1.0, "y": 0.5, "z": 2.047}
    assert out["gps_11"] == {"latitude": 31.0409, "longitude": 31.3785, "altitude": 12.5}
    assert len(out) == len(sample)
    assert len(lpp) == sum(2 + cayenne.BY_NAME[n].size for n in sample)


def test_half_step_rounds_away_from_zero_not_half_even():
    # round(26.85 / 0.1) == 268 in Python; the codec must say 269 like the C encoder does
    assert CayenneLPP().temperature(1, 26.85).bytes.hex() == "0167010d"
    assert CayenneLPP().temperature(1, -26.85).bytes.hex() == "0167fef3"
    assert CayenneLPP().humidity(1, 60.25).bytes.hex() == "016879"


def test_range_and_size_errors():
    with pytest.raises(ValueError, match="outside"):
        CayenneLPP().humidity(1, 128.0)
    with pytest.raises(ValueError, match="outside"):
        CayenneLPP().temperature(1, 3300.0)
    with pytest.raises(ValueError, match="takes 3"):
        CayenneLPP().add(1, "gps", 1.0)
    with pytest.raises(ValueError, match="channel"):
        CayenneLPP().temperature(256, 1.0)
    small = CayenneLPP(max_bytes=6).temperature(1, 1.0)
    with pytest.raises(ValueError, match="exceed 6"):
        small.humidity(2, 1.0)


def test_decode_rejects_bad_frames():
    with pytest.raises(ValueError, match="unknown CayenneLPP type 0x99"):
        decode(bytes.fromhex("019900"))
    with pytest.raises(ValueError, match="truncated temperature"):
        decode(bytes.fromhex("016701"))
    with pytest.raises(ValueError, match="truncated item header"):
        decode(bytes.fromhex("01"))
    assert decode(b"") == {}
