# Host-side checks, no board needed.  `make check` is what CI runs first.
PY ?= python3
CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -O1
export PYTHONPATH := src
CODEC_DIR = lib/payload_codec
CODEC_SRC = $(wildcard $(CODEC_DIR)/*.c)
CODEC_HDR = $(wildcard $(CODEC_DIR)/*.h)

.PHONY: check lint pytest test-core test-js pio-test vectors example build clean

check: lint pytest test-core test-js

lint:
	ruff check src tests tools && ruff format --check src tests tools

# Python unit tests + the C and JavaScript cross-checks (which compile/run via subprocess).
pytest:
	$(PY) -m pytest -q

# The C encoder against the shared vectors, plain cc.
test-core: build/test_codec
	./build/test_codec

build/test_codec: test/test_native/test_codec.c test/minitest.h $(CODEC_SRC) $(CODEC_HDR)
	@mkdir -p build
	$(CC) $(CFLAGS) -I$(CODEC_DIR) -Itest test/test_native/test_codec.c $(CODEC_SRC) -o $@

# The TTN/ChirpStack decoder against the shared vectors.
test-js:
	node decoder/test_decoder.js

# Same C tests, run by PlatformIO (needs the registry reachable to fetch the native platform).
pio-test:
	pio test -e native

# Regenerate tests/vectors.json and lib/payload_codec/test_vectors.h after a codec change.
vectors:
	$(PY) -m lorawan_payload_codec vectors

# The README tables (bytes of the real incubator readings, airtime per SF).
example:
	$(PY) -m lorawan_payload_codec example

# Firmware (needs the espressif32 platform; CI does this, the cloud sandbox cannot flash).
build:
	pio run -e esp32dev

clean:
	rm -rf build .pio .pytest_cache .ruff_cache
