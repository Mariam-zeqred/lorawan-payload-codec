"""Build examples/incubator_sample.json from the real queen-bee incubator log kept in
github.com/Mariam-zeqred/incubator-telemetry-analysis (data/hive-1C5A00_history_2026-10-03.json,
1 367 readings at 15 s from one afternoon).  Usage:

    python tools/make_sample.py \
        ../incubator-telemetry-analysis/data/hive-1C5A00_history_2026-10-03.json

One reading every 10 minutes is kept.  The logger is mains-powered and has no alarm output, so
two fields are not measured: battery is fixed at 3.60 V (illustrative) and alarm_code is derived
by the rule in `alarm_code()` below (0 none, 1 more than 2 degC below target, 2 more than 2 degC
above target, 3 door open).  The README says so wherever these values appear.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STEP_S = 600
BATTERY_V = 3.60


def alarm_code(row: dict) -> int:
    if row["door"] != "shut":
        return 3
    diff = row["temp"] - row["targetTemp"]
    if diff < -2:
        return 1
    if diff > 2:
        return 2
    return 0


def main(src: str, dst: str = "examples/incubator_sample.json") -> None:
    rows = json.loads(Path(src).read_text())
    out, next_ts = [], rows[0]["ts"]
    for row in rows:
        if row["ts"] < next_ts:
            continue
        next_ts = row["ts"] + STEP_S
        out.append(
            {
                "iso": row["iso"],
                "temperature_c": row["temp"],
                "humidity_pct": row["hum"],
                "battery_v": BATTERY_V,
                "door_open": row["door"] != "shut",
                "alarm_code": alarm_code(row),
                "target_c": row["targetTemp"],
                "heater": row["heater"],
            }
        )
    Path(dst).write_text(json.dumps({"source": Path(src).name, "readings": out}, indent=1) + "\n")
    print(f"{len(out)} readings -> {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:])
