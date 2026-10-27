#pragma once

struct Reading {
  float airTempC;        // DHT22 air temperature
  float humidityPct;     // DHT22 relative humidity
  int   soilRaw;         // averaged raw ADC value (kept for calibration/ML)
  float soilMoisturePct; // 0 = dry sample, 100 = wet sample
  bool  dhtOk;           // false if the DHT22 could not be read
};

void    sensorsBegin();
int     readSoilRaw();      // averaged raw ADC value
Reading readSensors();      // full measurement
