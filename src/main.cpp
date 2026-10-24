// ESP32 sketch: read the sensors, build the uplink frame with lib/payload_codec, hand it to the
// LoRaWAN stack.  The radio library is deliberately not included: `send_uplink()` is the one
// place to call your stack (LMIC, RadioLib, Heltec...) with (fport, buf, len).  Until then it
// prints the frame as hex, which `python -m lorawan_payload_codec decode <hex>` reads back.
//
// Built by CI for esp32dev; not flashed by the cloud session that wrote it.
#include <Arduino.h>
#include <Wire.h>

#include "Config.h"
#include "compact_codec.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

static bool read_sht31(int32_t *temp_centi, uint16_t *hum_centi) {
  // single-shot, high repeatability, clock stretching off (command 0x2400), then 6 bytes
  Wire.beginTransmission(0x44);
  Wire.write(0x24);
  Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;
  delay(16);
  if (Wire.requestFrom(0x44, 6) != 6) return false;
  uint8_t d[6];
  for (int i = 0; i < 6; i++) d[i] = Wire.read();
  uint32_t t = ((uint32_t)d[0] << 8) | d[1];
  uint32_t h = ((uint32_t)d[3] << 8) | d[4];
  // datasheet: T = -45 + 175 * t / 65535 ; RH = 100 * h / 65535, kept in integer centi-units
  *temp_centi = (int32_t)(-4500 + (17500LL * t) / 65535);
  *hum_centi = (uint16_t)((10000LL * h) / 65535);
  return true;
}

static uint16_t read_battery_mv() {
  uint32_t mv = analogReadMilliVolts(PIN_BATTERY_ADC);
  return (uint16_t)(mv * BATTERY_DIVIDER);
}

static uint8_t alarm_code(bool sensor_ok, int32_t temp_centi, bool door_open) {
  if (!sensor_ok) return ALARM_SENSOR_FAULT;
  if (door_open) return ALARM_DOOR_OPEN;
  if (temp_centi < TARGET_TEMP_CENTI - ALARM_BAND_CENTI) return ALARM_TOO_COLD;
  if (temp_centi > TARGET_TEMP_CENTI + ALARM_BAND_CENTI) return ALARM_TOO_HOT;
  return ALARM_NONE;
}

static void send_uplink(uint8_t fport, const uint8_t *buf, int len) {
  // TODO(hardware): e.g. LMIC_setTxData2(fport, (uint8_t *)buf, len, 0) with LMIC, or node.sendReceive(buf, len, fport) with RadioLib
  Serial.printf("FPort %u  %d B  ", fport, len);
  for (int i = 0; i < len; i++) Serial.printf("%02x", buf[i]);
  Serial.println();
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  pinMode(PIN_DOOR, INPUT_PULLUP);
  Serial.printf("lorawan-payload-codec node, DevEUI %s\n", LORAWAN_DEV_EUI);
}

void loop() {
  node_reading_t r = {0, 0, 0, 0, 0};
  bool ok = read_sht31(&r.temp_centi, &r.hum_centi);
  r.door_open = digitalRead(PIN_DOOR) == HIGH;
  r.batt_mv = read_battery_mv();
  r.alarm_code = alarm_code(ok, r.temp_centi, r.door_open);
  if (r.batt_mv < 2000) r.batt_mv = 2000;  // the compact frame's floor; a dead cell reads as 2.00 V
  if (r.batt_mv > 4550) r.batt_mv = 4550;

  uint8_t buf[CAYENNE_FRAME_SIZE];
#if USE_COMPACT_FRAME
  int len = compact_encode(&r, buf);
  uint8_t fport = FPORT_COMPACT;
#else
  int len = cayenne_frame_encode(&r, buf, sizeof buf);
  uint8_t fport = FPORT_CAYENNE;
#endif
  if (len < 0)
    Serial.println("reading out of range, frame not sent");
  else
    send_uplink(fport, buf, len);
  delay(UPLINK_INTERVAL_S * 1000UL);  // replace with deep sleep on a battery node
}
