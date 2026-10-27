#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>
#include "config.h"
#include "farm_net.h"

static WiFiClient   wifiClient;
static PubSubClient mqtt(wifiClient);

bool wifiConnect() {
  if (WiFi.status() == WL_CONNECTED) return true;

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(250);
  }
  return WiFi.status() == WL_CONNECTED;
}

bool timeIsValid() {
  return time(nullptr) >= MIN_VALID_EPOCH;
}

bool timeSync() {
  if (timeIsValid()) return true;
  configTime(0, 0, "pool.ntp.org", "time.google.com");  // UTC
  uint32_t start = millis();
  while (!timeIsValid() && millis() - start < NTP_TIMEOUT_MS) {
    delay(250);
  }
  return timeIsValid();
}

static bool mqttConnect() {
  if (mqtt.connected()) return true;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  return mqtt.connect(DEVICE_ID);
}

bool mqttPublishData(const char* payload) {
  if (!wifiConnect() || !mqttConnect()) return false;
  bool ok = mqtt.publish(TOPIC_DATA, payload);
  mqtt.loop();   // lets the library send the packet before we move on
  return ok;
}

void networkShutdown() {
  mqtt.disconnect();
  WiFi.disconnect(true);
}
