// Host helper for tests/test_c_roundtrip.py: reads "temp_centi hum_centi batt_mv door alarm"
// lines on stdin and prints "<compact hex> <cayenne hex>" (or "ERR ERR") per line, so Python
// can compare the C encoder with its own output on thousands of inputs.
#include <stdio.h>

#include "cayenne_lpp.h"
#include "compact_codec.h"

static void print_hex(const uint8_t *b, int n) {
  if (n < 0) {
    printf("ERR");
    return;
  }
  for (int i = 0; i < n; i++) printf("%02x", b[i]);
}

int main(void) {
  long t, h, b, d, a;
  while (scanf("%ld %ld %ld %ld %ld", &t, &h, &b, &d, &a) == 5) {
    node_reading_t r = {(int32_t)t, (uint16_t)h, (uint16_t)b, (uint8_t)d, (uint8_t)a};
    uint8_t buf[CAYENNE_FRAME_SIZE];
    print_hex(buf, compact_encode(&r, buf));
    putchar(' ');
    print_hex(buf, cayenne_frame_encode(&r, buf, sizeof buf));
    putchar('\n');
  }
  return 0;
}
