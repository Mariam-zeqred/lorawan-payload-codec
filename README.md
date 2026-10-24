# lorawan-payload-codec

Two uplink formats for a LoRaWAN sensor node that reports temperature, humidity, battery, door
state and an alarm code: standard **CayenneLPP** (17 bytes, self-describing) and a **compact
5-byte frame** designed here. Each format is implemented three times, in Python (the reference
and the test driver), in C for the ESP32 (integer-only, host-testable) and in JavaScript as a
payload formatter for The Things Stack or ChirpStack, and the tests prove the three agree byte
for byte. This repo shows how the bytes of an uplink are chosen and what they cost in airtime.

```
 sensor node (ESP32, C)                      network server            application
 SHT31 ─┐                                    ┌──────────────┐
 door  ─┼─> node_reading_t ─> compact_encode ─> FPort 1, 5 B ─┐    │ TTN / ChirpStack │   {temperature_c,
 ADC   ─┘   (integer units)   cayenne_frame  ─> FPort 2, 17 B ─┴──> │ decoder.js       ├─> humidity_pct, battery_v,
                                                                     └──────────────┘    door_open, alarm_code}
 Python: lorawan_payload_codec.encode/decode = the reference; vectors.json ties all three together
```

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt                 # pytest + ruff; the library itself is stdlib only
make check                                      # ruff, 35 pytest, C host test (cc), JS test (node)
make example                                    # the two tables below, from the real sample
PYTHONPATH=src python -m lorawan_payload_codec encode --temp 26.87 --hum 81.5 --batt 3.6 --alarm 1
PYTHONPATH=src python -m lorawan_payload_codec decode 410a7fa3a0
PYTHONPATH=src python -m lorawan_payload_codec airtime --per-day 144
pio test -e native                              # the same C tests under PlatformIO
pio run -e esp32dev                             # firmware compile (CI does this; not flashed here)
```

To use the decoder, paste `decoder/decoder.js` into the TTN console (Payload formatters,
Uplink, Custom JavaScript) or ChirpStack (Device profile, Codec). The firmware chooses the
format with `USE_COMPACT_FRAME` in `include/Config.h`; the FPort tells the decoder which one
arrived.

## The bytes

**Compact frame, FPort 1, 5 bytes** (`src/lorawan_payload_codec/compact.py`,
`lib/payload_codec/compact_codec.c`):

| byte | content | step / range |
|---|---|---|
| 0 | bits 7..6 version (= 1), bit 5 door open, bits 4..0 alarm code | alarm 0..31 |
| 1..2 | temperature, int16 big-endian | 0.01 °C, -327.68 .. 327.67 |
| 3 | relative humidity, uint8 | 0.5 %, 0 .. 100 |
| 4 | battery, uint8, counted from 2.00 V | 10 mV, 2.00 .. 4.55 V |

The first real reading in the sample, 26.87 °C, 81.5 %, 3.60 V, door shut, alarm 1, is
`41 0a7f a3 a0`: `0x41` = version 1, door shut, alarm 1; `0x0a7f` = 2687; `0xa3` = 163 half
percent; `0xa0` = 160 × 10 mV above 2.00 V.

**CayenneLPP, FPort 2, 17 bytes**: five items of `[channel][type][data]` on fixed channels,
temperature (0x67, 0.1 °C) on 1, humidity (0x68, 0.5 %) on 2, battery as analog input (0x02,
0.01 V) on 3, door as digital input (0x00) on 4 and the alarm code as digital input on 5. The
same reading is `01 67 010d | 02 68 a3 | 03 02 0168 | 04 00 00 | 05 00 01`. Note the temperature
is now 26.9 °C: CayenneLPP's step is 0.1 °C. The Python `CayenneLPP` class and the JavaScript
decoder also cover the other published types (digital/analog out, luminosity, presence,
barometer, accelerometer, gyrometer, GPS); the C encoder covers the 1- and 2-byte ones.

Every reading below is a real queen-bee incubator measurement (one every 10 minutes from the
log in [incubator-telemetry-analysis](https://github.com/Mariam-zeqred/incubator-telemetry-analysis),
`examples/incubator_sample.json`). Two fields are not in that log: the battery is fixed at an
illustrative 3.60 V (the logger is mains powered) and the alarm code is derived by the rule in
`tools/make_sample.py` (1 = more than 2 °C below target, 2 = above). Output of `make example`:

| time | temp | hum | batt | door | alarm | compact (FPort 1) | CayenneLPP (FPort 2) |
|---|---|---|---|---|---|---|---|
| 13:01:51 | 26.87 | 81.5 | 3.60 | 0 | 1 | `410a7fa3a0` | `0167010d0268a303020168040000050001` |
| 13:51:53 | 32.21 | 71.1 | 3.60 | 0 | 0 | `400c958ea0` | `0167014202688e03020168040000050000` |
| 14:41:56 | 30.45 | 69.1 | 3.60 | 0 | 0 | `400be58aa0` | `0167013102688a03020168040000050000` |
| 15:31:58 | 34.38 | 71.4 | 3.60 | 0 | 0 | `400d6e8fa0` | `0167015802688f03020168040000050000` |
| 16:22:01 | 37.72 | 70.9 | 3.60 | 0 | 0 | `400ebc8ea0` | `0167017902688e03020168040000050000` |
| 17:12:10 | 38.68 | 67.7 | 3.60 | 0 | 0 | `400f1c87a0` | `0167018302688703020168040000050000` |
| 18:02:13 | 38.61 | 67.3 | 3.60 | 0 | 0 | `400f1587a0` | `0167018202688703020168040000050000` |

## What the 12 bytes cost: airtime

Time on air from the SX1276 formula (the `airtime()` function is copied unchanged from
[lora-link-budget](https://github.com/Mariam-zeqred/lora-link-budget) and re-tested here against
The Things Network's published figures), EU868, 125 kHz, 13 bytes of LoRaWAN overhead, one
uplink every 10 minutes (144 per day). TTN's fair-use policy allows 30 s of uplink airtime per
device per day:

| SF | compact 5 B ms | s/day | CayenneLPP 17 B ms | s/day |
|---|---|---|---|---|
| 7 | 51.5 | 7.4 | 71.9 | 10.4 |
| 8 | 92.7 | 13.3 | 123.4 | 17.8 |
| 9 | 185.3 | 26.7 | 226.3 | 32.6 (over) |
| 10 | 329.7 | 47.5 (over) | 452.6 | 65.2 (over) |
| 11 | 659.5 | 95.0 (over) | 905.2 | 130.4 (over) |
| 12 | 1318.9 | 189.9 (over) | 1646.6 | 237.1 (over) |

The compact frame saves 12 of 30 PHY bytes, which is 20 to 30 % of airtime depending on the
spreading factor (the preamble and the 13 LoRaWAN bytes are fixed). At a 10-minute cadence it
stays inside the fair-use limit up to SF9 where CayenneLPP stops at SF8; at SF12 neither does,
so a far node must send less often. The regulatory 1 % duty cycle (864 s/day) is not the limit
in either case.

## Tests, and how the three implementations are kept identical

`src/lorawan_payload_codec/vectors.py` builds one list of 45 vectors (the 35 real readings plus
10 edge cases: range limits, negative temperature, half steps in both signs, door open, alarm
31) and writes it as `tests/vectors.json` and `lib/payload_codec/test_vectors.h`. A pytest
fails if the committed files are stale.

- `make pytest`: 35 tests. CayenneLPP against the reference byte examples (27.2 °C is
  `03 67 01 10`), the compact layout, range errors, the airtime formula against TTN's figures,
  the CLI, and two cross-language tests: `tests/test_c_roundtrip.py` compiles
  `tools/codec_dump.c` and checks that the C encoder produces the same bytes as Python for the
  45 vectors and for 2 000 seeded random readings, and `tests/test_js_decoder.py` runs the node
  test.
- `make test-core`: `test/test_native/test_codec.c`, 540 checks: every vector's bytes, compact
  decode round trip, refused out-of-range inputs, the generic LPP item writer. The same file
  runs under `pio test -e native`.
- `make test-js`: `decoder/test_decoder.js`, 639 checks: every vector decodes to Python's
  values on both ports, the generic LPP keys match TTN's naming (`temperature_3`), GPS and the
  error paths.

The one subtle point is rounding. `round(26.85 / 0.1)` is 268 in Python (26.85/0.1 is
268.4999… in binary floating point) but the C encoder, which only has the integer 2685, gives
269. Both encoders therefore use one rule, exact decimal, halves away from zero
(`rounding.py`, `rounding.h`), and a vector pins it.

## Limitations

- The firmware was not flashed by the session that wrote it, and the PlatformIO registry was
  not reachable from that sandbox, so `pio test -e native` and `pio run -e esp32dev` are
  exercised by CI only (the C tests ran locally with `cc`). The SHT31, door and battery reads
  in `src/main.cpp` follow the datasheets and are unverified on a board, and no LoRaWAN radio
  library is bound (`send_uplink()` prints the frame instead).
- The compact frame has no checksum of its own; LoRaWAN's MIC already protects the frame, and
  the version bits only catch a format change, not a corrupted byte.
- CayenneLPP in C covers 1- and 2-byte types only (no GPS, accelerometer, gyrometer); Python
  and JavaScript cover the full published list but none of the vendor extensions.
- Airtime is EU868 at 125 kHz; US915's 400 ms dwell limit and the regional payload caps are in
  lora-link-budget, not here.

## Next steps

- Downlinks: a 3-byte set-point frame (`encodeDownlink` in the formatter, `compact_decode`
  already exists in C) so the target temperature can be changed over the air.
- Bind a radio library in `send_uplink()`, flash, and compare the gateway's reported airtime
  with the table above.
- A delta-encoded frame for high-rate logging: send the first reading in full and then signed
  1-byte differences.
