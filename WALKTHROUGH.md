# Walkthrough (for Mariam)

## Why it is built this way

Every uplink byte costs airtime, so battery, the EU duty cycle and TTN's 30 s/day fair-use
limit. A codec is a contract between three programs in three languages: the firmware that
packs the bytes, the network server's JavaScript formatter that unpacks them, and the laptop
code that tests both. If they disagree by one bit the dashboard shows a plausible wrong number
and nobody notices. The design makes disagreement impossible to miss.

Python is the reference and generates the shared test vectors from 35 real incubator readings
plus edge cases. The C encoder works in integer units (centi-degrees, millivolts), so the ESP32
never needs a float, and a test proves it emits exactly Python's bytes. The JavaScript decoder
is checked against the same vectors with node. CayenneLPP is offered because every network
server understands it; the compact frame because it is 5 bytes instead of 17.

## File map

- `src/lorawan_payload_codec/cayenne.py`: table-driven CayenneLPP; `TYPES` gives each type
  byte its fields, `add` quantises and appends, `decode` names items like TTN does.
- `compact.py`: the 5-byte layout and the `Reading` dataclass. `frames.py`: FPort 1 =
  compact, FPort 2 = CayenneLPP on channels 1..5.
- `rounding.py` and `lib/payload_codec/rounding.h`: the one shared rounding rule.
- `airtime.py`: copied unchanged from lora-link-budget. `vectors.py`: builds the 45 vectors.
  `cli.py`: `encode`, `decode`, `airtime`, `example` (the README tables), `vectors`.
- `lib/payload_codec/`: `cayenne_lpp.c` (generic range-checked items), `compact_codec.c`
  (both frames from one `node_reading_t`, plus compact decode). `test/test_native/` is the C
  host test; `tools/codec_dump.c` is what the Python cross-check feeds random readings.
- `decoder/decoder.js`: `decodeUplink` for TTN v3 / ChirpStack v4, `Decode` for ChirpStack v3.
- `src/main.cpp`, `include/Config.h`, `include/secrets.example.h`: the ESP32 sketch.

## Three questions a professor may ask

**CayenneLPP already exists. Why design your own frame?**
CayenneLPP spends 2 header bytes per value, so five values carry 10 bytes of labels for
7 bytes of data. The node always sends the same five fields, so the compact frame drops the
labels and lets the FPort and two version bits say which layout it is. The saving is 12 bytes,
20 to 30 % of airtime, and at a 10-minute cadence it is the difference between staying inside
TTN's fair-use limit at SF9 or not. The cost is a private format: the decoder must be installed and
a change needs a version bump.

**How do you know the C code on the board produces the same bytes as your Python?**
Python generates 45 vectors from real readings and edge cases; the C test compiles them in and
asserts the hex matches; a second test pushes 2 000 random readings through a small C program
and compares hex strings with Python; node decodes every vector and compares values. The
vectors are committed and a test fails if they are stale, so a codec change shows in the diff.
This caught one real bug: `round(26.85/0.1)` is 268 in floating point but 269 in integer
arithmetic, so both languages now use one rule, exact decimal, halves away from zero.

**Why no checksum in the compact frame, and why 0.5 % humidity steps?**
LoRaWAN already has a 4-byte MIC and a PHY CRC, so a corrupted frame is dropped before the
decoder sees it. The version bits are not integrity; they stop a decoder reading an older
firmware's layout. Humidity at 0.5 % matches the SHT31's ±2 % accuracy and CayenneLPP's step,
so one byte is enough; temperature keeps 0.01 °C because the incubator control loop works in
hundredths. Resolution should follow what the data is for, not what the sensor can print.

## One thing to extend

Add downlinks: a 3-byte set-point frame (flags, int16 target in 0.01 °C) so the incubator
target can be changed over the air. `compact_decode` in C shows the pattern, `decoder.js`
needs an `encodeDownlink(input)`, and a downlink vector file keeps the three sides honest.
