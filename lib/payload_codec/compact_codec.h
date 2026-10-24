// The node's two uplink frames, built from one integer reading.  Layouts and channel numbers
// mirror src/lorawan_payload_codec/{compact,frames}.py; see README "The bytes".
//
//   compact (FPort 1, 5 bytes)
//     0     bits 7..6 version = 1 | bit 5 door open | bits 4..0 alarm code
//     1..2  temperature int16 BE, 0.01 degC
//     3     humidity uint8, 0.5 %
//     4     battery uint8, 10 mV above 2.00 V
//   CayenneLPP (FPort 2, 17 bytes)
//     ch1 temperature, ch2 humidity, ch3 analog_in battery V, ch4 digital_in door,
//     ch5 digital_in alarm code
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define COMPACT_VERSION 1
#define COMPACT_SIZE 5
#define CAYENNE_FRAME_SIZE 17
#define FPORT_COMPACT 1
#define FPORT_CAYENNE 2

#ifndef LPP_CH_TEMPERATURE  // Config.h may override the channel plan
#define LPP_CH_TEMPERATURE 1
#define LPP_CH_HUMIDITY 2
#define LPP_CH_BATTERY 3
#define LPP_CH_DOOR 4
#define LPP_CH_ALARM 5
#endif

typedef struct {
  int32_t temp_centi;  // 0.01 degC
  uint16_t hum_centi;  // 0.01 %
  uint16_t batt_mv;
  uint8_t door_open;   // 0 / 1
  uint8_t alarm_code;  // 0..31
} node_reading_t;

// Both return the frame length, or -1 when a value is out of range or `cap` is too small
// (nothing is written then).
int compact_encode(const node_reading_t *r, uint8_t out[COMPACT_SIZE]);
int cayenne_frame_encode(const node_reading_t *r, uint8_t *out, uint8_t cap);

// Inverse of compact_encode; hum_centi comes back as a multiple of 50 and batt_mv of 10.
// Returns 0, or -1 for a wrong length or version.
int compact_decode(const uint8_t *buf, uint8_t len, node_reading_t *r);

#ifdef __cplusplus
}
#endif
