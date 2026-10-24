"""Byte-exact agreement between the C encoder (lib/payload_codec) and the Python encoder.

tools/codec_dump.c is compiled with the system C compiler, fed every shared vector plus 2 000
seeded random readings in the integer units the firmware has, and its hex output must equal
Python's; Python then decodes the C bytes back to the quantised reading.  Skipped, loudly, when
no C compiler is on the PATH (CI has one)."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from lorawan_payload_codec import frames, vectors
from lorawan_payload_codec.compact import Reading

ROOT = vectors.ROOT
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


@pytest.fixture(scope="module")
def dump_binary(tmp_path_factory) -> Path:
    if CC is None:
        pytest.skip("no C compiler on PATH; `make test-core` needs one")
    exe = tmp_path_factory.mktemp("c") / "codec_dump"
    sources = [
        str(ROOT / "tools" / "codec_dump.c"),
        *map(str, (ROOT / "lib/payload_codec").glob("*.c")),
    ]
    subprocess.run(
        [
            CC,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "lib/payload_codec"),
            *sources,
            "-o",
            str(exe),
        ],
        check=True,
    )
    return exe


def _c_encode(exe: Path, readings: list[Reading]) -> list[tuple[str, str]]:
    lines = [
        f"{round(r.temperature_c * 100)} {round(r.humidity_pct * 100)} {round(r.battery_v * 1000)} "
        f"{int(r.door_open)} {r.alarm_code}"
        for r in readings
    ]
    out = subprocess.run(
        [str(exe)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True
    )
    return [tuple(line.split()) for line in out.stdout.splitlines()]  # type: ignore[misc]


def test_shared_vectors(dump_binary):
    vs = json.loads(vectors.JSON_OUT.read_text())
    got = _c_encode(dump_binary, [Reading(**v["input"]) for v in vs])
    assert got == [(v["compact"]["hex"], v["cayenne"]["hex"]) for v in vs]


def test_random_readings_agree_and_decode(dump_binary):
    rng = random.Random(2026)
    readings = [
        Reading(
            temperature_c=rng.randint(-32768, 32767) / 100,
            humidity_pct=rng.randint(0, 10000) / 100,
            battery_v=rng.randint(2000, 4550) / 1000,
            door_open=rng.random() < 0.3,
            alarm_code=rng.randint(0, 31),
        )
        for _ in range(2000)
    ]
    got = _c_encode(dump_binary, readings)
    assert len(got) == len(readings)
    for r, (c_hex, y_hex) in zip(readings, got, strict=True):
        assert frames.encode(r, "compact")[1].hex() == c_hex, r
        assert frames.encode(r, "cayenne")[1].hex() == y_hex, r
        back = frames.decode(frames.FPORT_COMPACT, bytes.fromhex(c_hex))
        assert back.temperature_c == r.temperature_c
        assert abs(back.humidity_pct - r.humidity_pct) <= 0.25
        assert abs(back.battery_v - r.battery_v) <= 0.005 + 1e-9
        assert (back.door_open, back.alarm_code) == (r.door_open, r.alarm_code)


def test_c_and_python_refuse_the_same_readings(dump_binary):
    # compact has a 2.00 V floor and an int16 centi-degC range that CayenneLPP does not have;
    # humidity above 100 % and an alarm code above 31 are refused by both formats
    cases = [
        Reading(0, 0, 1.999, False),
        Reading(0, 100.01, 3.0, False),
        Reading(400, 0, 3.0, False),
        Reading(20, 50, 3.0, False, 32),
    ]
    got = _c_encode(dump_binary, cases)
    assert got == [
        ("ERR", "01670000026800030200c8040000050000"),
        ("ERR", "ERR"),
        ("ERR", "01670fa0026800030201 2c040000050000".replace(" ", "")),
        ("ERR", "ERR"),
    ]
    for r, (c_hex, y_hex) in zip(cases, got, strict=True):
        for fmt, hexval in (("compact", c_hex), ("cayenne", y_hex)):
            if hexval == "ERR":
                with pytest.raises(ValueError):
                    frames.encode(r, fmt)
            else:
                assert frames.encode(r, fmt)[1].hex() == hexval
