// CayenneLPP encoder: [channel][type][big-endian data].  Values are passed in integer sensor
// units (centi-degC, centi-percent, millivolts) and rounded to the LPP step here, so the
// firmware never touches floating point.  Every add returns the bytes appended, or -1 when the
// value does not fit the field or the buffer is full (the frame is then left unchanged).
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  LPP_DIGITAL_IN = 0x00,   // 1 byte
  LPP_DIGITAL_OUT = 0x01,  // 1 byte
  LPP_ANALOG_IN = 0x02,    // int16, 0.01
  LPP_ANALOG_OUT = 0x03,   // int16, 0.01
  LPP_LUMINOSITY = 0x65,   // uint16, 1 lux
  LPP_PRESENCE = 0x66,     // 1 byte
  LPP_TEMPERATURE = 0x67,  // int16, 0.1 degC
  LPP_HUMIDITY = 0x68,     // uint8, 0.5 %
  LPP_BAROMETER = 0x73,    // uint16, 0.1 hPa
};

typedef struct {
  uint8_t *buf;
  uint8_t cap;
  uint8_t len;
} lpp_t;

void lpp_init(lpp_t *lpp, uint8_t *buf, uint8_t cap);

// Generic item: `raw` is already in LSB units; `size` is 1 or 2 bytes; `is_signed` selects the
// range check (int8/int16 vs uint8/uint16).
int lpp_add_raw(lpp_t *lpp, uint8_t channel, uint8_t type, int32_t raw, uint8_t size,
                uint8_t is_signed);

int lpp_add_digital_in(lpp_t *lpp, uint8_t channel, uint8_t value);
int lpp_add_analog_in(lpp_t *lpp, uint8_t channel, int32_t milli);      // e.g. mV -> 0.01 V
int lpp_add_temperature(lpp_t *lpp, uint8_t channel, int32_t centi_degc);
int lpp_add_humidity(lpp_t *lpp, uint8_t channel, uint32_t centi_pct);

#ifdef __cplusplus
}
#endif
