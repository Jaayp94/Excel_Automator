# evaluation.py
import os
import csv
from datetime import datetime
from collections import defaultdict

PHASES = ["VAR_StartZeit", "VAR_StationsZeit", "VAR_ArbeitsZeit_Station", "VAR_Return"]
SAVE_PATH = "./csv_logs"

# Status pro Station/Phase
timing_state = defaultdict(lambda: {phase: {"active": False, "start_time": None} for phase in PHASES})

def evaluate_logic(station_configs, current_state):
    """
    Erwartetes station_configs-Format (pro Station):
    {
      "station": "<Name>",
      "logic": [
        {
          "step": <int>,
          "target": "VAR_StartZeit" | "VAR_StationsZeit" | "VAR_ArbeitsZeit_Station" | "VAR_Return",
          "vars": [
             { "name": "VAR_X", "not": true/false, "op": "UND"|"ODER" },  # op wirkt zwischen bisherigem Ergebnis und dieser Variable
             { "name": "VAR_Y", "not": false, "op": "ODER" },
             ...
          ]
        },
        ...
      ]
    }
    """
    for station, config in station_configs.items():
        if station not in timing_state:
            timing_state[station] = {phase: {"active": False, "start_time": None} for phase in PHASES}

        for phase in PHASES:
            # Liste (wert_bool, op_str) pro Variable dieser Phase aufbauen
            values_ops = []
            for block in config.get("logic", []):
                if block.get("target") != phase:
                    continue
                for v in block.get("vars", []):
                    val = bool(current_state.get(v.get("name"), 0))
                    val = (not val) if v.get("not") else val
                    op = (v.get("op") or "UND").upper()
                    if op not in ("UND", "ODER"):
                        op = "UND"
                    values_ops.append((val, op))

            if not values_ops:
                # Nichts konfiguriert -> Phase nicht aktiv
                _end_if_active_and_log(station, phase)
                continue

            # Links-faltend auswerten: result op value
            result = values_ops[0][0]
            for (val, op) in values_ops[1:]:
                if op == "ODER":
                    result = result or val
                else:  # "UND" (Default)
                    result = result and val

            # Zeit-Start/Stop + CSV
            state = timing_state[station][phase]
            if result and not state["active"]:
                state["active"] = True
                state["start_time"] = datetime.now()
            elif not result and state["active"]:
                end_time = datetime.now()
                start_time = state.get("start_time")
                if start_time is not None:
                    duration = (end_time - start_time).total_seconds()
                    log_phase_time(station, phase, start_time, end_time, duration)
                state["active"] = False
                state["start_time"] = None

def _end_if_active_and_log(station, phase):
    """Hilfsfunktion: Falls Phase aktiv war, sauber beenden und loggen."""
    state = timing_state[station][phase]
    if state["active"]:
        end_time = datetime.now()
        start_time = state.get("start_time")
        if start_time is not None:
            duration = (end_time - start_time).total_seconds()
            log_phase_time(station, phase, start_time, end_time, duration)
        state["active"] = False
        state["start_time"] = None

def apply_logic(values, logic):
    # Wird in der neuen per-Variable-Operator-Logik nicht mehr benötigt,
    # bleibt aber kompatibel falls anderswo verwendet.
    if logic == "UND":
        return all(values)
    elif logic == "ODER":
        return any(values)
    elif logic == "UND NICHT":
        return all(values[:-1]) and not values[-1] if len(values) >= 2 else False
    return False

def log_phase_time(station, phase, start, end, duration):
    if not os.path.exists(SAVE_PATH):
        os.makedirs(SAVE_PATH)
    filename = os.path.join(SAVE_PATH, f"{station}.csv")
    file_exists = os.path.isfile(filename)
    with open(filename, mode="a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["Timestamp", "Phase", "Start", "End", "Duration_s"])
        writer.writerow([datetime.now().isoformat(), phase, start.time(), end.time(), round(duration, 3)])

def get_phase_status():
    """Liefert { station: { phase: bool_active, ... }, ... }"""
    out = {}
    for station, phases in timing_state.items():
        out[station] = {p: bool(phases[p]["active"]) for p in PHASES}
    return out
