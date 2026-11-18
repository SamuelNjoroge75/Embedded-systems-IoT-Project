"""
Cloud & Dashboard
Subscribes to the farm node's MQTT topic, stores every reading in SQLite,
and serves the dashboard + a small JSON/CSV API.

Run:  python server.py
Open: http://localhost:5000
"""
import csv, io, json, math, os, sqlite3, threading, time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, request, send_from_directory

# ---- Settings (override with environment variables) -------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "strathmore/group3b/#")   # must match the firmware
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
SOIL_MIN = float(os.getenv("SOIL_MIN", "30"))     # % below which we raise "soil too dry"
OFFLINE_AFTER = int(os.getenv("OFFLINE_AFTER", "120"))  # seconds without data = offline
DB_PATH = os.getenv("DB_PATH", "farm.db")
MERGE_WINDOW = int(os.getenv("MERGE_WINDOW", "600"))  # seconds: readings this close together count as "current"
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


def to_num(v):
    """Number (or numeric string like "24.0") -> float/int, anything else -> None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        try:
            v = float(v)
        except ValueError:
            return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return v
    return None


def store_message(topic, payload_bytes):
    """Accepts a JSON object with numeric fields, OR a plain number on a per-sensor
    topic such as strathmore/group3b/farm_node_1/temperature."""
    try:
        text = payload_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False
    parts = topic.rstrip("/").split("/")
    try:
        obj = json.loads(text)
    except ValueError:
        obj = to_num(text)
        if obj is None:
            print(f"[mqtt] ignored unreadable payload on {topic}")
            return False
    if isinstance(obj, dict):
        data = {k: n for k, v in obj.items() if k != "ts" and (n := to_num(v)) is not None}
        node = str(obj.get("node_id") or obj.get("node") or obj.get("device") or parts[-1])
    else:
        n = to_num(obj)
        if n is None or len(parts) < 2:
            return False
        data = {parts[-1]: n}
        node = parts[-2]
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
def is_soil(key):
    k = key.lower()
    return ("soil" in k or "moist" in k) and "temp" not in k


def alerts_for(data):
    return [{"type": "soil_dry",
             "message": f"Soil too dry - {k.replace('_', ' ')} {v:.1f}% (limit {SOIL_MIN:g}%)"}
            for k, v in data.items() if is_soil(k) and v < SOIL_MIN]


def merged_latest(con, node):
    """Newest value of EVERY field for a node, even if the fields arrive in separate messages."""
    rows = con.execute("SELECT ts,data FROM readings WHERE node=? ORDER BY id DESC LIMIT 500", (node,))
    newest, merged = None, {}
    for r in rows:
        if newest is None:
            newest = r["ts"]
        if newest - r["ts"] > MERGE_WINDOW:
            break
        for k, v in json.loads(r["data"]).items():
            merged.setdefault(k, v)
    return newest, merged


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
            ts, data = merged_latest(con, n)
            result[n] = {"ts": ts, "online": now - ts <= OFFLINE_AFTER,
                         "data": dict(sorted(data.items())), "alerts": alerts_for(data)}
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
