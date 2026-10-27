#include <Arduino.h>
#include <DHT.h>
#include "config.h"
#include "sensors.h"

static DHT dht(PIN_DHT, DHT22);

void sensorsBegin() {
  dht.begin();
  analogReadResolution(12);                    // 0-4095
  analogSetPinAttenuation(PIN_SOIL, ADC_11db); // measure up to ~3.3 V
}

int readSoilRaw() {
  long sum = 0;
  for (int i = 0; i < SOIL_SAMPLES; i++) {
    sum += analogRead(PIN_SOIL);
    delay(10);
  }
  return (int)(sum / SOIL_SAMPLES);
}

static float rawToPercent(int raw) {
  float pct = (float)(SOIL_DRY_RAW - raw) * 100.0f /
              (float)(SOIL_DRY_RAW - SOIL_WET_RAW);
  return constrain(pct, 0.0f, 100.0f);
}

// The DHT22 can fail occasionally and needs ~2 s between reads, so retry.
static bool readDht(float &t, float &h) {
  for (int attempt = 0; attempt < 3; attempt++) {
    t = dht.readTemperature();
    h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) return true;
    delay(2000);
  }
  return false;
}

Reading readSensors() {
  Reading r;
  r.dhtOk = readDht(r.airTempC, r.humidityPct);
  r.soilRaw = readSoilRaw();
  r.soilMoisturePct = rawToPercent(r.soilRaw);
  return r;
}
