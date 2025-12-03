from flask import Flask, render_template, request, jsonify, send_from_directory
import threading
import time
import os
from typing import Dict, Any

# Deine Logikfunktionen
from logic.evaluation import evaluate_logic, get_phase_status  # unverändert verwenden

app = Flask(__name__, static_folder='static', template_folder='templates')
# --------------------------------------------------------------------
# Globale Zustände
# --------------------------------------------------------------------
station_configs: Dict[str, Any] = {}   # Konfigurationen pro Station (vom Frontend)
current_state: Dict[str, Any] = {}     # letzter bekannter SPS-Zustand (via /ingest geliefert)

# --------------------------------------------------------------------
# Hilfsfunktionen: robustes Parsen verschiedener Formate
# (vereinfacht & fokussiert auf JSON-Map, akzeptiert aber auch "name=value"-Zeilen)
# --------------------------------------------------------------------
def _coerce_bool_or_number(v):
    if isinstance(v, (int, float, bool)):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "wahr", "on", "an", "yes", "y"):
        return 1
    if s in ("0", "false", "falsch", "off", "aus", "no", "n"):
        return 0
    try:
        # dezimaltrennzeichen tolerant
        s2 = s.replace(",", ".")
        return float(s2) if "." in s2 else int(s2)
    except Exception:
        return 1 if s else 0

def _parse_state_payload(content_type, text_or_json):
    """
    Erwartete Standardnutzung: JSON-Objekt { "VarA": 1, "VarB": 0, ... }
    Fällt ansonsten auf einfache Zeilen ("Name=Value") zurück.
    """
    import json
    ct = (content_type or "").lower()
    # JSON
    if "json" in ct or isinstance(text_or_json, (dict, list)):
        data = text_or_json
        if isinstance(text_or_json, str):
            try:
                data = json.loads(text_or_json)
            except Exception:
                return {}
        if isinstance(data, dict):
            return {str(k): _coerce_bool_or_number(v) for k, v in data.items()}
        # Liste von {name, value}-Objekten
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            out = {}
            for it in data:
                name = None
                for nk in ("name", "variable", "id"):
                    if nk in it:
                        name = str(it[nk]); break
                if not name:
                    continue
                val = None
                for vk in ("value", "val", "status", "state"):
                    if vk in it:
                        val = _coerce_bool_or_number(it[vk]); break
                if val is None:
                    val = 1
                out[name] = val
            return out
        return {}
    # Plain Text: Zeilenweise "Name=Value"
    text = text_or_json or ""
    out = {}
    for line in str(text).splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        for sep in ("=", ";", ",", "\t"):
            if sep in s:
                n, v = s.split(sep, 1)
                out[n.strip()] = _coerce_bool_or_number(v.strip())
                break
        else:
            out[s] = 1
    return out

# --------------------------------------------------------------------
# Routen
# --------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ingest", methods=["POST"])
def ingest():
    """
    Webhook für den FlowCreator (oder beliebige Sender).

    Beispiele:
      JSON-Body (empfohlen):
        { "Station1_Start": 1, "Roboter_Bereit": 0, "Sensor_34": 1 }

      Alternativ (text/plain):
        Station1_Start=1
        Roboter_Bereit=0
        Sensor_34=1
    """
    global current_state
    try:
        # Versuche JSON, sonst Plaintext
        if request.is_json:
            payload = request.get_json(silent=True)
            state = _parse_state_payload("application/json", payload)
        else:
            state = _parse_state_payload(request.headers.get("Content-Type", ""), request.get_data(as_text=True))

        if not isinstance(state, dict) or not state:
            return jsonify({"ok": False, "error": "Ungueltiger oder leerer State"}), 400

        current_state = state
        # Logik bewerten (aktualisiert interne Phasenstatus-Struktur in evaluation.py)
        evaluate_logic(station_configs, current_state)
        return jsonify({"ok": True, "variables": len(current_state)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/variables", methods=["GET"])
def api_variables():
    """
    Liefert Variablennamen aus dem zuletzt empfangenen Zustand.
    Optional: ?filter=...  & ?limit=...
    """
    flt = (request.args.get("filter") or "").strip().lower()
    try:
        limit = max(1, min(int(request.args.get("limit", "200")), 2000))
    except ValueError:
        limit = 200

    names = sorted(current_state.keys())
    if flt:
        names = [n for n in names if flt in n.lower()]
    return jsonify(names[:limit])

@app.route("/phase_status", methods=["GET"])
def phase_status():
    """
    Gibt den aktuellen Phasenstatus je Station zurück.
    Form: { "<Stationsname>": { "VAR_StartZeit": true/false, ... }, ... }
    """
    return jsonify(get_phase_status())

@app.route("/config", methods=["POST"])
def config():
    data = request.get_json(silent=True) or {}
    station_name = data.get("station")
    if station_name:
        station_configs[station_name] = data
        return jsonify({"status": "ok", "saved": station_name})
    return jsonify({"status": "error", "message": "No station name"}), 400

@app.route("/download", methods=["GET"])
def download_csv():
    station = request.args.get("station")
    if not station:
        return "Fehlender Stationsname", 400
    file_path = os.path.join("csv_logs", f"{station}.csv")
    if not os.path.exists(file_path):
        return "Datei nicht gefunden", 404
    return send_from_directory("csv_logs", f"{station}.csv", as_attachment=True)

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "variables": len(current_state),
        "stations": list(station_configs.keys())
    })

# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
if __name__ == "__main__":
    # Kein Hintergrund-Polling mehr nötig – Daten kommen per /ingest an
    app.run(host="0.0.0.0", port=8080)
