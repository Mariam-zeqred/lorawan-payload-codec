// Tuning for the ESP32 sketch (src/main.cpp).  Nothing here is secret; keys go in secrets.h.
#pragma once

#define UPLINK_INTERVAL_S 600     // one uplink every 10 minutes = 144 per day
#define USE_COMPACT_FRAME 1       // 1: FPort 1, 5 bytes.  0: FPort 2, CayenneLPP, 17 bytes
#define SERIAL_BAUD 115200

// Sensor wiring (SHT31 on I2C, reed switch on the door, battery divider on an ADC pin)
#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22
#define PIN_DOOR 27               // reed switch to GND, INPUT_PULLUP: HIGH = door open
#define PIN_BATTERY_ADC 34
#define BATTERY_DIVIDER 2.0f      // (R1 + R2) / R2 of the measuring divider

// Alarm codes (bits 4..0 of the compact flags byte; CayenneLPP channel 5)
#define ALARM_NONE 0
#define ALARM_TOO_COLD 1          // chamber more than ALARM_BAND_CENTI below target
#define ALARM_TOO_HOT 2
#define ALARM_DOOR_OPEN 3
#define ALARM_SENSOR_FAULT 4
#define ALARM_BAND_CENTI 200      // 2.00 degC
#define TARGET_TEMP_CENTI 3200    // 32.00 degC (queen-bee incubator set point)

// CayenneLPP channel plan.  Must match decoder/decoder.js (CH) and frames.py.
#define LPP_CH_TEMPERATURE 1
#define LPP_CH_HUMIDITY 2
#define LPP_CH_BATTERY 3
#define LPP_CH_DOOR 4
#define LPP_CH_ALARM 5
