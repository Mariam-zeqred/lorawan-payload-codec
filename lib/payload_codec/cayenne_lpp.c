#include "cayenne_lpp.h"

#include "rounding.h"

void lpp_init(lpp_t *lpp, uint8_t *buf, uint8_t cap) {
  lpp->buf = buf;
  lpp->cap = cap;
  lpp->len = 0;
}

int lpp_add_raw(lpp_t *lpp, uint8_t channel, uint8_t type, int32_t raw, uint8_t size,
                uint8_t is_signed) {
  if (size != 1 && size != 2) return -1;
  int32_t lo = is_signed ? -(1L << (8 * size - 1)) : 0;
  int32_t hi = is_signed ? (1L << (8 * size - 1)) - 1 : (1L << (8 * size)) - 1;
  if (raw < lo || raw > hi) return -1;
  if (lpp->len + 2 + size > lpp->cap) return -1;
  uint8_t *p = lpp->buf + lpp->len;
  *p++ = channel;
  *p++ = type;
  uint32_t u = (uint32_t)raw;  // two's complement, big-endian
  if (size == 2) *p++ = (uint8_t)(u >> 8);
  *p++ = (uint8_t)u;
  lpp->len += 2 + size;
  return 2 + size;
}

int lpp_add_digital_in(lpp_t *lpp, uint8_t channel, uint8_t value) {
  return lpp_add_raw(lpp, channel, LPP_DIGITAL_IN, value, 1, 0);
}

int lpp_add_analog_in(lpp_t *lpp, uint8_t channel, int32_t milli) {
  return lpp_add_raw(lpp, channel, LPP_ANALOG_IN, div_round_away(milli, 10), 2, 1);
}

int lpp_add_temperature(lpp_t *lpp, uint8_t channel, int32_t centi_degc) {
  return lpp_add_raw(lpp, channel, LPP_TEMPERATURE, div_round_away(centi_degc, 10), 2, 1);
}

int lpp_add_humidity(lpp_t *lpp, uint8_t channel, uint32_t centi_pct) {
  if (centi_pct > 10000) return -1;  // 0..100 %
  return lpp_add_raw(lpp, channel, LPP_HUMIDITY, div_round_away((int32_t)centi_pct, 50), 1, 0);
}
