#include <Arduino.h>
#include <ArduinoJson.h>
#include <time.h>
#include "config.h"
#include "sensors.h"
#include "farm_net.h"

// Survives deep sleep, so the dashboard can spot missing messages.
RTC_DATA_ATTR uint32_t seq = 0;

// Round to 1 decimal so the JSON reads 24.6 and not 24.600000381.
static double round1(float v) {
  return round((double)v * 10.0) / 10.0;
}

static bool buildPayload(const Reading &r, char *out, size_t len) {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["seq"]       = seq;
  doc["ts"]        = (uint32_t)time(nullptr);   // UTC epoch seconds

  if (r.dhtOk) {
    doc["air_temp_c"]   = round1(r.airTempC);
    doc["humidity_pct"] = round1(r.humidityPct);
  } else {                                      // keep the soil data anyway
    doc["air_temp_c"]   = nullptr;
    doc["humidity_pct"] = nullptr;
  }
  doc["soil_raw"]      = r.soilRaw;
  doc["soil_moist_pct"] = round1(r.soilMoisturePct);

  size_t n = serializeJson(doc, out, len);
  return n > 0 && n < len;
}

static void doCycle() {
  if (!timeIsValid() && wifiConnect()) timeSync();   // retry clock if it failed

  Reading r = readSensors();

  char payload[320];
  if (!buildPayload(r, payload, sizeof(payload))) {
    Serial.println("Payload too large, skipping");
    return;
  }
  Serial.println(payload);

  bool sent = false;
  for (int attempt = 1; attempt <= 3 && !sent; attempt++) {
    sent = mqttPublishData(payload);
    if (!sent) {
      Serial.printf("Publish attempt %d failed\n", attempt);
      delay(1000 * attempt);                          // back off a little more each time
    }
  }
  Serial.println(sent ? "Published" : "Gave up this cycle");
  seq++;
}

static void goToSleep() {
  networkShutdown();
  esp_sleep_enable_timer_wakeup((uint64_t)CYCLE_SECONDS * 1000000ULL);
  esp_deep_sleep_start();                             // never returns
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nFarm node starting");

  sensorsBegin();
  if (CALIBRATION_MODE) return;

  if (wifiConnect()) timeSync();
  else Serial.println("Wi-Fi failed, will retry each cycle");

  if (USE_DEEP_SLEEP) {
    doCycle();
    goToSleep();
  }
}

void loop() {
  if (CALIBRATION_MODE) {
    Serial.printf("soil raw = %d\n", readSoilRaw());
    delay(500);
    return;
  }
  doCycle();
  delay(CYCLE_SECONDS * 1000UL);
}
