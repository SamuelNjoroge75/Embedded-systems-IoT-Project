# Firmware: Farm IoT Node

**Embedded Systems and IoT Group Project**


This is the ESP32 firmware for our smart-farm data collection prototype. Every minute the device measures soil moisture, air temperature and humidity, then sends the readings over Wi-Fi to a cloud broker (MQTT) as a small JSON message. The data feeds the dashboard and, in future, the AI advisory system for smallholder farmers in Busia County.

## What it does

1. **Measures** soil moisture (capacitive sensor) and air temperature and humidity (DHT22).
2. **Packs** the readings with the device ID, a message number and a timestamp into JSON.
3. **Sends** the JSON over Wi-Fi to an MQTT broker, retrying up to 3 times if it fails.
4. **Waits** for the next cycle (60 seconds by default), then repeats.

## Hardware and wiring

| Part | Pin | Notes |
|---|---|---|
| ESP32 dev board | | Board selected in Arduino IDE: *ESP32 Dev Module* |
| DHT22 (air temp and humidity) | GPIO 15 | 3.3 V power |
| Capacitive soil moisture sensor | GPIO 34 | Analog output, 3.3 V power. GPIO 34 is on ADC1, which keeps working while Wi-Fi is on |

In the Wokwi simulation, a potentiometer on GPIO 34 stands in for the soil sensor.

## Files

| File | Purpose |
|---|---|
| `farm_node.ino` | Main program: runs one measure-build-send cycle, then waits |
| `config.h` | All settings in one place: pins, calibration, timings, MQTT details |
| `secrets.h` | Wi-Fi name and password. **Not on GitHub**, each person creates their own |
| `secrets.example.h` | Template for `secrets.h` with placeholder values |
| `sensors.h` / `sensors.cpp` | Reads and averages the sensors, converts soil to a percentage |
| `farm_net.h` / `farm_net.cpp` | Connects to Wi-Fi, syncs the clock, sends MQTT messages |
| `libraries.txt` | Library list for the Wokwi simulator |

Each `.h` file lists what a part offers, and the matching `.cpp` file holds the code. The main file only talks to those lists, so a part such as Wi-Fi can be swapped for GSM without touching the rest.

## How it works

```
setup()  → start sensors → join Wi-Fi → get time from internet (NTP)
loop()   → read sensors → build JSON → send (up to 3 tries) → wait 60 s
```

- **Soil moisture:** the sensor is read 10 times and averaged, because the ESP32's analog input is noisy. The average is converted to a percentage using two calibration points (see below).
- **Air readings:** the DHT22 is retried up to 3 times, because it fails occasionally. If it still fails, the air values are sent as `null` and the soil data is still sent.
- **Time:** the clock is set from NTP in UTC. The timestamp is sent as epoch seconds, meaning seconds since 1 January 1970. The dashboard converts it to East Africa Time.
- **Sending:** the message is published with MQTT. If Wi-Fi or the broker is unreachable, it retries with a growing delay (1, 2, then 3 seconds) and gives up for that cycle if all three fail.

### MQTT topic

```
strathmore/4d/busia/<DEVICE_ID>/data
```

`DEVICE_ID` is set in `config.h` (example: `g4d-farm-node-01`). The cloud and dashboard side subscribes to this topic.

### Message format

```json
{"device_id":"g4d-farm-node-01","seq":12,"ts":1761130000,"air_temp_c":24.6,"humidity_pct":61.2,"soil_raw":2310,"soil_moist_pct":49.5}
```

| Field | Meaning |
|---|---|
| `device_id` | Which device sent it |
| `seq` | Message counter, so lost messages can be spotted |
| `ts` | Time of reading, UTC epoch seconds |
| `air_temp_c` | Air temperature in °C (`null` if the DHT22 failed) |
| `humidity_pct` | Relative humidity in % (`null` if the DHT22 failed) |
| `soil_raw` | Averaged raw sensor value (kept for calibration and future model training) |
| `soil_moist_pct` | Soil moisture, 0 to 100 % relative to our dry and wet samples |

## Settings (`config.h`)

| Setting | What it does | Default |
|---|---|---|
| `DEVICE_ID` | Unique name for this device, also used in the topic | `g4d-farm-node-01` |
| `MQTT_HOST`, `MQTT_PORT` | Broker address and port | `broker.hivemq.com`, `1883` |
| `PIN_DHT`, `PIN_SOIL` | GPIO pins for the sensors | `15`, `34` |
| `SOIL_DRY_RAW`, `SOIL_WET_RAW` | Calibration values (see below) | `3200`, `1400` (placeholders) |
| `SOIL_SAMPLES` | Readings averaged per measurement | `10` |
| `CYCLE_SECONDS` | Time between measurements | `60` |
| `USE_DEEP_SLEEP` | Sleep between cycles to save power (for battery or solar) | `false` |
| `CALIBRATION_MODE` | Only print raw soil values, for calibration | `false` |

## Soil calibration

The soil percentage is a **relative** value: 0 % is our dry sample and 100 % is our saturated sample. Capacitive sensors read *lower* when wetter.

1. Set `CALIBRATION_MODE = true` in `config.h` and upload. The Serial Monitor (115200 baud) prints `soil raw = ...` twice a second.
2. Put the sensor in dry soil, wait about 15 seconds for the reading to settle, and note the value. This is `SOIL_DRY_RAW`.
3. Put the sensor in the same soil soaked until saturated and note the value. This is `SOIL_WET_RAW`.
4. Enter both numbers in `config.h`, set `CALIBRATION_MODE = false`, and upload again.
5. Check a half-wet sample. It should read roughly 40 to 60 %.

Use the same soil in both samples and push the sensor to the same depth each time.

```
soil % = (SOIL_DRY_RAW − reading) ÷ (SOIL_DRY_RAW − SOIL_WET_RAW) × 100
```

## Design choices and alternatives

| Part | We used | Alternatives considered |
|---|---|---|
| Soil sensor | Capacitive analog, two-point calibration | Resistive (corrodes in wet soil), I2C soil sensors |
| Air sensor | DHT22 | DHT11 (less accurate), BME280 (adds pressure) |
| Time | NTP over Wi-Fi | DS3231 real-time clock for offline use |
| Transport | Wi-Fi | GSM or LoRa, better suited to rural fields without Wi-Fi |
| Protocol | MQTT | HTTP POST |
| Payload | JSON | CSV line, compact binary for low-bandwidth links |
| Power | Always on | Deep sleep with solar and battery (supported by `USE_DEEP_SLEEP`) |

We chose Wi-Fi and MQTT because they are simple to build and test within the project time. GSM or LoRa would be the realistic choice for field deployment.

## Limitations and future work

- Readings are not stored on the device. If sending fails three times, that cycle's data is lost. Buffering to an SD card is a possible improvement.
- Soil moisture is relative, not true volumetric water content. Lab calibration (weighing and oven-drying samples) would improve accuracy.
- Plain MQTT on a public broker is not encrypted and anyone can read the topic. A private broker with TLS (port 8883) and a login would be needed for real use.
- Rainfall and soil temperature sensors are not included.
- The device runs on mains or USB power. Solar and deep sleep would be needed in the field.
