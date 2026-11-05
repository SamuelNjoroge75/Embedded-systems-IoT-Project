# Cloud & Dashboard (Group 4D)

MQTT subscriber + SQLite database + web dashboard for the Busia farm node.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python server.py
```

Open http://localhost:5000

## Test with simulated data

In a second terminal (same venv):

```bash
python simulator.py
```

## Connect the real device

The firmware (`farm_node/`) must publish JSON to a topic that matches `MQTT_TOPIC`:

```json
{"node_id":"farm_node_1","soil_moisture":41.2,"temperature":24.8,"humidity":63.0,"rain":0.0}
```

If the firmware uses a different broker or topic, set it without editing code:

```bash
set MQTT_HOST=broker.hivemq.com
set MQTT_TOPIC=your/topic/#
set SOIL_MIN=30
python server.py
```

(Linux/Mac: `export` instead of `set`.)

## What it does

- Live readings update every 3 seconds, online/offline status per node
- History chart (1 h / 24 h / 7 d) for any metric
- Alert banner: "Soil too dry" when soil moisture drops below `SOIL_MIN` (default 30)
- Download CSV button (`/api/export.csv`)
- Any numeric JSON field the device sends shows up automatically

## Files

- `server.py` - MQTT subscriber, SQLite storage, API
- `static/index.html` - dashboard
- `simulator.py` - fake device
- `mosquitto.conf` - optional local broker config
