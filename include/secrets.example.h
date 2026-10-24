// Copy to include/secrets.h and fill in from your LoRaWAN network server (TTN / ChirpStack).
// include/secrets.h is git-ignored.  OTAA keys, MSB first, as the console shows them.
#pragma once

#define LORAWAN_DEV_EUI "0000000000000000"
#define LORAWAN_APP_EUI "0000000000000000"  // "JoinEUI" in TTN v3
#define LORAWAN_APP_KEY "00000000000000000000000000000000"
