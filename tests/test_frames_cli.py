import json

import pytest

from lorawan_payload_codec import frames
from lorawan_payload_codec.cli import main
from lorawan_payload_codec.compact import Reading

R = Reading(31.95, 70.5, 3.60, True, 3)


def test_cayenne_frame_layout_and_ports():
    fport, b = frames.encode(R, "cayenne")
    assert fport == 2
    # ch1 temp 320 (0x0140) | ch2 hum 141 | ch3 batt 360 (0x0168) | ch4 door 1 | ch5 alarm 3
    assert b.hex() == "01670140" + "02688d" + "03020168" + "040001" + "050003"
    assert len(b) == 17
    assert frames.decode(2, b) == Reading(32.0, 70.5, 3.6, True, 3)  # 0.1 degC step in LPP
    assert frames.encode(R, "compact") == (1, bytes.fromhex("630c7b8da0"))
    assert frames.decode(1, bytes.fromhex("630c7b8da0")) == R


def test_errors():
    with pytest.raises(ValueError, match="format"):
        frames.encode(R, "json")
    with pytest.raises(ValueError, match="FPort 9"):
        frames.decode(9, b"")
    with pytest.raises(ValueError, match="lacks the node's field"):
        frames.from_cayenne(bytes.fromhex("01670140"))


def test_cli_encode_decode_json(capsys):
    args = "--temp 31.95 --hum 70.5 --batt 3.6 --door --alarm 3 --json".split()
    main(["encode", *args])
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["hex"] for line in lines] == ["630c7b8da0", "0167014002688d03020168040001050003"]
    main(["decode", "630c7b8da0", "--json"])
    assert json.loads(capsys.readouterr().out) == {"fport": 1, **R.as_dict()}
    main(["decode", "0167014002688d03020168040001050003"])
    assert "temperature_c=32.0" in capsys.readouterr().out


def test_cli_airtime_and_example_run(capsys):
    main(["airtime", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert [r["sf"] for r in rows] == [7, 8, 9, 10, 11, 12]
    assert rows[0]["compact_ms"] == 51.5 and rows[0]["cayenne_ms"] == 71.9
    main(["example", "--every", "10"])
    out = capsys.readouterr().out
    assert "35 real incubator readings" in out and "| 12 |" in out
