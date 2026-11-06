"""
Cloud & Dashboard
Subscribes to the farm node's MQTT topic, stores every reading in SQLite,
and serves the dashboard + a small JSON/CSV API.

Run:  python server.py
Open: http://localhost:5000
"""
import csv, io, json, os, sqlite3, threading, time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, request, send_from_directory

# ---- Settings (override with environment variables) -------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "strathmore/group4d/#")   # must match the firmware
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
SOIL_MIN = float(os.getenv("SOIL_MIN", "30"))     # % below which we raise "soil too dry"
OFFLINE_AFTER = int(os.getenv("OFFLINE_AFTER", "120"))  # seconds without data = offline
DB_PATH = os.getenv("DB_PATH", "farm.db")
# -----------------------------------------------------------------------------

app = Flask(__name__, static_folder="static")


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS readings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL, node TEXT NOT NULL, data TEXT NOT NULL)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_node_ts ON readings(node, ts)")


# ---- MQTT -------------------------------------------------------------------
def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[mqtt] connected ({reason_code}), subscribing to {MQTT_TOPIC}")
    client.subscribe(MQTT_TOPIC)


def store_message(topic, payload_bytes):
    """Accepts any flat JSON object; keeps numeric fields only."""
    try:
        obj = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        print(f"[mqtt] ignored non-JSON on {topic}")
        return False
    if not isinstance(obj, dict):
        return False
    data = {k: v for k, v in obj.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}
    node = str(obj.get("node_id") or obj.get("node") or obj.get("device")
               or topic.rstrip("/").split("/")[-1])
    data.pop("ts", None)
    if not data:
        return False
    with db() as con:
        con.execute("INSERT INTO readings(ts,node,data) VALUES(?,?,?)",
                    (int(time.time()), node, json.dumps(data)))
    print(f"[mqtt] {node}: {data}")
    return True


def on_message(client, userdata, msg):
    store_message(msg.topic, msg.payload)


def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()


# ---- Helpers ----------------------------------------------------------------
def soil_key(data):
    for k in data:
        if "soil" in k.lower() or "moist" in k.lower():
            return k
    return None


def alerts_for(data):
    out = []
    k = soil_key(data)
    if k is not None and data[k] < SOIL_MIN:
        out.append({"type": "soil_dry", "message": f"Soil too dry ({data[k]:.1f}% < {SOIL_MIN:g}%)"})
    return out


# ---- API --------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/latest")
def latest():
    now = int(time.time())
    result = {}
    with db() as con:
        nodes = [r["node"] for r in con.execute("SELECT DISTINCT node FROM readings")]
        for n in nodes:
            r = con.execute("SELECT ts,data FROM readings WHERE node=? ORDER BY id DESC LIMIT 1", (n,)).fetchone()
            data = json.loads(r["data"])
            result[n] = {"ts": r["ts"], "online": now - r["ts"] <= OFFLINE_AFTER,
                         "data": data, "alerts": alerts_for(data)}
    return jsonify({"soil_min": SOIL_MIN, "nodes": result})


@app.get("/api/history")
def history():
    node = request.args.get("node", "")
    hours = float(request.args.get("hours", 24))
    since = int(time.time() - hours * 3600)
    with db() as con:
        rows = con.execute("SELECT ts,data FROM readings WHERE node=? AND ts>=? ORDER BY ts DESC LIMIT 1500",
                           (node, since)).fetchall()
    rows.reverse()
    return jsonify([{"ts": r["ts"], "data": json.loads(r["data"])} for r in rows])


@app.get("/api/export.csv")
def export_csv():
    node = request.args.get("node")
    q, args = "SELECT ts,node,data FROM readings", ()
    if node:
        q, args = q + " WHERE node=?", (node,)
    with db() as con:
        rows = con.execute(q + " ORDER BY ts", args).fetchall()
    parsed = [(r["ts"], r["node"], json.loads(r["data"])) for r in rows]
    cols = sorted({k for _, _, d in parsed for k in d})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp_utc", "node"] + cols)
    for ts, n, d in parsed:
        iso = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        w.writerow([iso, n] + [d.get(c, "") for c in cols])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=farm_readings.csv"})


init_db()
if __name__ == "__main__":
    start_mqtt()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
