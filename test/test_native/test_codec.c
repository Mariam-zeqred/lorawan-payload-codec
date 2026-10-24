// Host tests for lib/payload_codec: every shared vector encodes to the bytes Python produced,
// the compact frame decodes back, and out-of-range inputs are refused.
//   make test-core          (plain cc)
//   pio test -e native      (PlatformIO native env, custom runner)
#include <stdio.h>
#include <string.h>

#include "cayenne_lpp.h"
#include "compact_codec.h"
#include "minitest.h"
#include "rounding.h"
#include "test_vectors.h"

static void to_hex(const uint8_t *b, int n, char *out) {
  for (int i = 0; i < n; i++) sprintf(out + 2 * i, "%02x", b[i]);
  out[2 * n] = 0;
}

static node_reading_t reading_of(const codec_vector_t *v) {
  node_reading_t r = {v->temp_centi, v->hum_centi, v->batt_mv, v->door_open, v->alarm_code};
  return r;
}

static void rounding_rule() {
  CHECK_EQ(div_round_away(2685, 10), 269);
  CHECK_EQ(div_round_away(-2685, 10), -269);
  CHECK_EQ(div_round_away(2684, 10), 268);
  CHECK_EQ(div_round_away(6025, 50), 121);
  CHECK_EQ(div_round_away(1615, 10), 162);
  CHECK_EQ(div_round_away(0, 10), 0);
}

static void vectors_match_python_bytes() {
  uint8_t buf[CAYENNE_FRAME_SIZE];
  char hex[2 * CAYENNE_FRAME_SIZE + 1];
  for (int i = 0; i < CODEC_N_VECTORS; i++) {
    const codec_vector_t *v = &CODEC_VECTORS[i];
    node_reading_t r = reading_of(v);
    int n = compact_encode(&r, buf);
    CHECK_EQ(n, COMPACT_SIZE);
    to_hex(buf, n, hex);
    CHECK_STR_EQ(hex, v->compact_hex);
    n = cayenne_frame_encode(&r, buf, sizeof buf);
    CHECK_EQ(n, CAYENNE_FRAME_SIZE);
    to_hex(buf, n, hex);
    CHECK_STR_EQ(hex, v->cayenne_hex);
  }
}

static void compact_round_trips_to_the_quantised_reading() {
  uint8_t buf[COMPACT_SIZE];
  for (int i = 0; i < CODEC_N_VECTORS; i++) {
    node_reading_t in = reading_of(&CODEC_VECTORS[i]), out;
    CHECK_EQ(compact_encode(&in, buf), COMPACT_SIZE);
    CHECK_EQ(compact_decode(buf, COMPACT_SIZE, &out), 0);
    CHECK_EQ(out.temp_centi, in.temp_centi);
    CHECK_EQ(out.hum_centi, div_round_away(in.hum_centi, 50) * 50);
    CHECK_EQ(out.batt_mv, 2000 + div_round_away(in.batt_mv - 2000, 10) * 10);
    CHECK_EQ(out.door_open, in.door_open);
    CHECK_EQ(out.alarm_code, in.alarm_code);
  }
}

static void first_incubator_reading_bytes() {
  // 26.87 degC, 81.5 %, 3.60 V, door shut, alarm 1  ->  41 0a7f a3 a0
  node_reading_t r = {2687, 8150, 3600, 0, 1};
  uint8_t buf[CAYENNE_FRAME_SIZE];
  CHECK_EQ(compact_encode(&r, buf), 5);
  CHECK_EQ(buf[0], 0x41);
  CHECK_EQ(buf[1], 0x0a);
  CHECK_EQ(buf[2], 0x7f);
  CHECK_EQ(buf[3], 163);
  CHECK_EQ(buf[4], 160);
  CHECK_EQ(cayenne_frame_encode(&r, buf, sizeof buf), 17);
  CHECK_EQ(buf[0], 1);     // channel 1
  CHECK_EQ(buf[1], 0x67);  // temperature
  CHECK_EQ(buf[2], 0x01);  // 269 = 0x010d
  CHECK_EQ(buf[3], 0x0d);
}

static void out_of_range_is_refused_and_leaves_buffer_untouched() {
  uint8_t buf[CAYENNE_FRAME_SIZE];
  memset(buf, 0xEE, sizeof buf);
  node_reading_t r = {2687, 8150, 3600, 0, 32};  // alarm 32
  CHECK_EQ(compact_encode(&r, buf), -1);
  CHECK_EQ(cayenne_frame_encode(&r, buf, sizeof buf), -1);
  r.alarm_code = 0;
  r.batt_mv = 1999;
  CHECK_EQ(compact_encode(&r, buf), -1);
  r.batt_mv = 4560;
  CHECK_EQ(compact_encode(&r, buf), -1);
  r.batt_mv = 3600;
  r.hum_centi = 10001;
  CHECK_EQ(compact_encode(&r, buf), -1);
  CHECK_EQ(cayenne_frame_encode(&r, buf, sizeof buf), -1);
  r.hum_centi = 5000;
  r.temp_centi = 40000;
  CHECK_EQ(compact_encode(&r, buf), -1);
  CHECK_EQ(buf[0], 0xEE);
  // a buffer one byte short of 17 is refused too
  r.temp_centi = 2000;
  CHECK_EQ(cayenne_frame_encode(&r, buf, CAYENNE_FRAME_SIZE - 1), -1);
}

static void lpp_generic_fields_and_signs() {
  uint8_t buf[16];
  lpp_t lpp;
  lpp_init(&lpp, buf, sizeof buf);
  CHECK_EQ(lpp_add_temperature(&lpp, 3, 2720), 4);  // 27.2 degC -> 03 67 01 10 (reference example)
  CHECK_EQ(lpp_add_temperature(&lpp, 5, -410), 4);  // -4.1 degC -> 05 67 ff d7
  CHECK_EQ(lpp_add_raw(&lpp, 6, LPP_BAROMETER, 10132, 2, 0), 4);
  char hex[33];
  to_hex(buf, lpp.len, hex);
  CHECK_STR_EQ(hex, "036701100567ffd70673" "2794");
  CHECK_EQ(lpp_add_raw(&lpp, 7, LPP_LUMINOSITY, 65536, 2, 0), -1);  // uint16 overflow
  CHECK_EQ(lpp_add_raw(&lpp, 7, LPP_ANALOG_IN, -32769, 2, 1), -1);  // int16 underflow
  CHECK_EQ(lpp_add_raw(&lpp, 7, LPP_DIGITAL_IN, 1, 3, 0), -1);      // bad size
  CHECK_EQ(lpp_add_digital_in(&lpp, 7, 1), 3);
  CHECK_EQ(lpp_add_digital_in(&lpp, 8, 1), -1);  // 15 of 16 bytes used
  CHECK_EQ(lpp.len, 15);
}

static void compact_decode_rejects_bad_frames() {
  node_reading_t r;
  uint8_t v2[5] = {0x80, 0, 0, 0, 0};
  CHECK_EQ(compact_decode(v2, 5, &r), -1);
  uint8_t ok[5] = {0x41, 0x0a, 0x7f, 163, 160};
  CHECK_EQ(compact_decode(ok, 4, &r), -1);
  CHECK_EQ(compact_decode(ok, 5, &r), 0);
  CHECK_EQ(r.temp_centi, 2687);
  CHECK_EQ(r.hum_centi, 8150);
  CHECK_EQ(r.batt_mv, 3600);
  uint8_t neg[5] = {0x60, 0xfb, 0x2e, 1, 1};  // door open, -12.34 degC
  CHECK_EQ(compact_decode(neg, 5, &r), 0);
  CHECK_EQ(r.temp_centi, -1234);
  CHECK_EQ(r.door_open, 1);
}

int main(void) {
  printf("payload_codec host tests (%d vectors)\n", CODEC_N_VECTORS);
  RUN(rounding_rule);
  RUN(vectors_match_python_bytes);
  RUN(compact_round_trips_to_the_quantised_reading);
  RUN(first_incubator_reading_bytes);
  RUN(out_of_range_is_refused_and_leaves_buffer_untouched);
  RUN(lpp_generic_fields_and_signs);
  RUN(compact_decode_rejects_bad_frames);
  return mt_summary();
}
