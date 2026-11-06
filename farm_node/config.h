#pragma once
#include <stdint.h>
#include <time.h>
#include "secrets.h"          // WIFI_SSID, WIFI_PASS (are not committed to GitHub)

// ---------- Identity and MQTT ----------
#define NODE_ID     "farm_node_1"                    //name shown on the dashboard
#define TOPIC_DATA    "strathmore/group3B/" NODE_ID  //login name on the broker, must be unique
#define MQTT_CLIENT_ID  "g3b-esp32-node-o1"
constexpr uint16_t MQTT_PORT = 1883;

// ---------- Pins ----------
constexpr int PIN_DHT  = 15;   // DHT22 data pin
constexpr int PIN_SOIL = 34;   // soil sensor analog out (ADC1, safe with Wi-Fi)

// ---------- Soil calibration (raw 12-bit ADC, 0-4095) ----------
// Replace with the real readings from your dry and wet samples on build day.
constexpr int SOIL_DRY_RAW = 3200;   // sensor in dry soil/air
constexpr int SOIL_WET_RAW = 1400;   // sensor in saturated soil
constexpr int SOIL_SAMPLES = 10;     // readings averaged per measurement

// ---------- Behaviour ----------
constexpr uint32_t CYCLE_SECONDS    = 120;      // one reading every 2 minutes
constexpr bool     USE_DEEP_SLEEP   = false;   // true for battery/solar later
constexpr bool     CALIBRATION_MODE = false;   // true to print raw soil values
constexpr uint32_t WIFI_TIMEOUT_MS  = 10000;
constexpr uint32_t NTP_TIMEOUT_MS   = 10000;
constexpr time_t   MIN_VALID_EPOCH  = 1700000000;  // anything earlier = clock not set
