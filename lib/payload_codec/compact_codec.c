#include "compact_codec.h"

#include "cayenne_lpp.h"
#include "rounding.h"

#define BATT_OFFSET_MV 2000
#define BATT_STEP_MV 10

int compact_encode(const node_reading_t *r, uint8_t out[COMPACT_SIZE]) {
  if (r->alarm_code > 31 || r->hum_centi > 10000) return -1;
  if (r->temp_centi < -32768 || r->temp_centi > 32767) return -1;
  if (r->batt_mv < BATT_OFFSET_MV || r->batt_mv > BATT_OFFSET_MV + 255 * BATT_STEP_MV) return -1;
  int32_t hum = div_round_away(r->hum_centi, 50);
  int32_t batt = div_round_away(r->batt_mv - BATT_OFFSET_MV, BATT_STEP_MV);
  if (hum > 255 || batt > 255) return -1;  // cannot happen after the checks above; keeps the cast honest
  out[0] = (uint8_t)((COMPACT_VERSION << 6) | (r->door_open ? 0x20 : 0) | r->alarm_code);
  out[1] = (uint8_t)((uint32_t)r->temp_centi >> 8);
  out[2] = (uint8_t)r->temp_centi;
  out[3] = (uint8_t)hum;
  out[4] = (uint8_t)batt;
  return COMPACT_SIZE;
}

int compact_decode(const uint8_t *buf, uint8_t len, node_reading_t *r) {
  if (len != COMPACT_SIZE || (buf[0] >> 6) != COMPACT_VERSION) return -1;
  r->door_open = (buf[0] >> 5) & 1;
  r->alarm_code = buf[0] & 0x1F;
  r->temp_centi = (int16_t)(((uint16_t)buf[1] << 8) | buf[2]);
  r->hum_centi = (uint16_t)(buf[3] * 50);
  r->batt_mv = (uint16_t)(BATT_OFFSET_MV + buf[4] * BATT_STEP_MV);
  return 0;
}

int cayenne_frame_encode(const node_reading_t *r, uint8_t *out, uint8_t cap) {
  // range checks first, so a bad reading never leaves a half-written frame
  if (r->alarm_code > 31 || r->hum_centi > 10000) return -1;
  if (r->temp_centi < -327680 || r->temp_centi > 327670) return -1;
  if (cap < CAYENNE_FRAME_SIZE) return -1;
  lpp_t lpp;
  lpp_init(&lpp, out, cap);
  if (lpp_add_temperature(&lpp, LPP_CH_TEMPERATURE, r->temp_centi) < 0 ||
      lpp_add_humidity(&lpp, LPP_CH_HUMIDITY, r->hum_centi) < 0 ||
      lpp_add_analog_in(&lpp, LPP_CH_BATTERY, r->batt_mv) < 0 ||
      lpp_add_digital_in(&lpp, LPP_CH_DOOR, r->door_open ? 1 : 0) < 0 ||
      lpp_add_digital_in(&lpp, LPP_CH_ALARM, r->alarm_code) < 0)
    return -1;
  return lpp.len;
}
