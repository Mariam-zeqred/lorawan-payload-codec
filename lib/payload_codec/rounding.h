// Integer division rounded half away from zero: the one rounding rule shared with the Python
// encoder (src/lorawan_payload_codec/rounding.py).  div_round_away(2685, 10) == 269 and
// div_round_away(-2685, 10) == -269, so 26.85 degC becomes 26.9 in CayenneLPP in both languages.
#pragma once
#include <stdint.h>

static inline int32_t div_round_away(int32_t n, int32_t d) {
  return n >= 0 ? (n + d / 2) / d : -((-n + d / 2) / d);
}
