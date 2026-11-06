"""
Fake farm node for testing the dashboard before the real ESP32 is ready.
Publishes the same JSON the firmware sends:
  {"node_id":"farm_node_1","soil_moisture":41.2,"temperature":24.8,"humidity":63.0,"rain":0.0}

Run:  python simulator.py            (one reading every 2 s)
      python simulator.py --interval 5
"""
import argparse, json, math, os, random, time
import paho.mqtt.client as mqtt

HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("SIM_TOPIC", "strathmore/farm/farm_node_1")

ap = argparse.ArgumentParser()
ap.add_argument("--interval", type=float, default=2.0)
args = ap.parse_args()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(HOST, PORT, 60)
client.loop_start()

soil, t = 60.0, 0
print(f"Publishing to {TOPIC} on {HOST}:{PORT} (Ctrl+C to stop)")
while True:
    soil -= random.uniform(0.2, 1.2)            # soil slowly dries out
    if soil < 12:                               # "irrigation / rain" refills it
        soil = random.uniform(55, 70)
    msg = {
        "node_id": "farm_node_1",
        "soil_moisture": round(soil, 1),
        "temperature": round(24 + 5 * math.sin(t / 30) + random.uniform(-0.3, 0.3), 1),
        "humidity": round(62 - 10 * math.sin(t / 30) + random.uniform(-1, 1), 1),
        "rain": 0.0 if random.random() > 0.05 else round(random.uniform(0.2, 2.0), 1),
    }
    client.publish(TOPIC, json.dumps(msg), qos=1)
    print(msg)
    t += 1
    time.sleep(args.interval)
