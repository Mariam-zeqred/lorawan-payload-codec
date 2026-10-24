"""Command line: encode a reading, decode a hex payload, print the airtime table or the
README's worked example from the real incubator sample."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from . import frames, vectors
from .airtime import airtime
from .compact import Reading

SFS = (7, 8, 9, 10, 11, 12)
TTN_FAIR_USE_S_PER_DAY = 30.0


def _reading(a: argparse.Namespace) -> Reading:
    return Reading(a.temp, a.hum, a.batt, a.door, a.alarm)


def cmd_encode(a: argparse.Namespace) -> None:
    r = _reading(a)
    for fmt in frames.FORMATS if a.format == "both" else (a.format,):
        fport, payload = frames.encode(r, fmt)
        seen = frames.decode(fport, payload)
        if a.json:
            print(
                json.dumps({"format": fmt, "fport": fport, "hex": payload.hex(), **seen.as_dict()})
            )
        else:
            print(f"{fmt:8s} FPort {fport}  {len(payload):2d} B  {payload.hex()}  -> {seen}")


def cmd_decode(a: argparse.Namespace) -> None:
    payload = bytes.fromhex(a.hex)
    by_length = frames.FPORT_COMPACT if len(payload) == 5 else frames.FPORT_CAYENNE
    fport = a.fport or by_length
    r = frames.decode(fport, payload)
    print(json.dumps({"fport": fport, **r.as_dict()}) if a.json else r)


def airtime_rows(sizes: dict[str, int], per_day: int, region_max_app: dict[int, int] | None = None):
    rows = []
    for sf in SFS:
        row: dict = {"sf": sf}
        for name, n in sizes.items():
            t = airtime(n, sf).total_ms
            row[f"{name}_ms"] = round(t, 1)
            row[f"{name}_s_per_day"] = round(t * per_day / 1000, 1)
        rows.append(row)
    return rows


def _fair(s_per_day: float) -> str:
    return f"{s_per_day}" + (" (over)" if s_per_day > TTN_FAIR_USE_S_PER_DAY else "")


def cmd_airtime(a: argparse.Namespace) -> None:
    sizes = {"compact": a.compact_bytes, "cayenne": a.cayenne_bytes}
    rows = airtime_rows(sizes, a.per_day)
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    c, y = sizes["compact"], sizes["cayenne"]
    print(
        f"EU868 125 kHz, {a.per_day} uplinks/day, TTN fair use {TTN_FAIR_USE_S_PER_DAY:.0f} s/day"
    )
    print(f"| SF | compact {c} B ms | s/day | CayenneLPP {y} B ms | s/day |")
    print("|---|---|---|---|---|")
    for r in rows:
        cd, yd = r["compact_s_per_day"], r["cayenne_s_per_day"]
        print(f"| {r['sf']} | {r['compact_ms']} | {_fair(cd)} | {r['cayenne_ms']} | {_fair(yd)} |")


def cmd_example(a: argparse.Namespace) -> None:
    sample = vectors.sample_readings()
    print(f"{len(sample)} real incubator readings (examples/incubator_sample.json), both formats:")
    print("| time | temp | hum | batt | door | alarm | compact (FPort 1) | CayenneLPP (FPort 2) |")
    print("|---|---|---|---|---|---|---|---|")
    for name, r in sample[:: a.every]:
        c = frames.encode(r, "compact")[1].hex()
        y = frames.encode(r, "cayenne")[1].hex()
        print(
            f"| {name[-8:]} | {r.temperature_c:.2f} | {r.humidity_pct:.1f} | {r.battery_v:.2f} | "
            f"{int(r.door_open)} | {r.alarm_code} | `{c}` | `{y}` |"
        )
    print()
    cmd_airtime(
        argparse.Namespace(compact_bytes=5, cayenne_bytes=17, per_day=a.per_day, json=False)
    )


def cmd_vectors(a: argparse.Namespace) -> None:
    for p in vectors.write():
        print(f"wrote {p.relative_to(vectors.ROOT)}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lorawan_payload_codec", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("encode", help="encode one reading")
    e.add_argument("--temp", type=float, required=True, help="degC")
    e.add_argument("--hum", type=float, required=True, help="%% RH")
    e.add_argument("--batt", type=float, required=True, help="volts")
    e.add_argument("--door", action="store_true", help="door open")
    e.add_argument("--alarm", type=int, default=0, help="alarm code 0..31")
    e.add_argument("--format", choices=(*frames.FORMATS, "both"), default="both")
    e.set_defaults(fn=cmd_encode)

    d = sub.add_parser("decode", help="decode a hex payload")
    d.add_argument("hex")
    d.add_argument(
        "--fport", type=int, default=0, help="1 compact, 2 CayenneLPP (default: by size)"
    )
    d.set_defaults(fn=cmd_decode)

    t = sub.add_parser("airtime", help="airtime per SF for the two frame sizes")
    t.add_argument("--compact-bytes", type=int, default=5)
    t.add_argument("--cayenne-bytes", type=int, default=17)
    t.add_argument("--per-day", type=int, default=144, help="uplinks per day (144 = every 10 min)")
    t.set_defaults(fn=cmd_airtime)

    x = sub.add_parser("example", help="the README tables from the real sample")
    x.add_argument("--every", type=int, default=5, help="print every n-th reading")
    x.add_argument("--per-day", type=int, default=144)
    x.set_defaults(fn=cmd_example)

    v = sub.add_parser("vectors", help="regenerate tests/vectors.json and test_vectors.h")
    v.set_defaults(fn=cmd_vectors)

    for s in (e, d, t):
        s.add_argument("--json", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> None:
    a = build_parser().parse_args(argv)
    a.fn(a)
