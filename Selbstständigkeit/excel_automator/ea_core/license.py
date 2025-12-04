# ea_core/license.py

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple, Union

# -------------------------------------------------------------------
# WICHTIG:
# Diesen Schlüssel solltest du für deine "Produktiv-Version"
# EINMAL zufällig generieren und dann nicht mehr ändern.
# Beispiel: os.urandom(32).hex().encode("utf-8")
# -------------------------------------------------------------------
SECRET_KEY = b"CHANGE_THIS_TO_A_RANDOM_SECRET_32_BYTES_OR_MORE"
APP_ID = "EXCEL_AUTOMATOR_PRO_V1"
LICENSE_VERSION = "L1"  # für spätere Erweiterungen


# -------------------------------------------------------------------
# Maschinen-ID
# -------------------------------------------------------------------

def get_machine_id() -> str:
    """
    Erzeugt eine relativ stabile Maschinen-ID auf Basis von Hostname und MAC.
    Die ID ist gehasht (kein Klartext-MAC) und 16 Zeichen lang.
    """
    try:
        node = platform.node()
    except Exception:
        node = "UNKNOWN_NODE"

    try:
        mac = uuid.getnode()
    except Exception:
        mac = 0

    raw = f"{node}-{mac}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    # 16 Zeichen reichen für eine eindeutige ID und sind gut kopierbar
    return digest[:16]


# -------------------------------------------------------------------
# Hilfsfunktionen
# -------------------------------------------------------------------

def _normalize_machine_id(machine_id: str) -> str:
    return machine_id.strip().upper()


def _build_payload(machine_id: str, expires_str: str) -> str:
    """
    Payload ist die Basis für die Signatur.
    """
    mid = _normalize_machine_id(machine_id)
    return f"{LICENSE_VERSION}|{APP_ID}|{mid}|{expires_str}"


def _sign_payload(payload: str) -> str:
    sig = hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()
    # Wir kürzen auf 16 Zeichen – reicht völlig, sieht aber nicht zu lang aus.
    return sig[:16]


def _parse_date_yyyy_mm_dd(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


# -------------------------------------------------------------------
# LIZENZ GENERIEREN (für dich / Generator-Skript)
# -------------------------------------------------------------------

def generate_license_key(machine_id: str, expires_on: Optional[str] = None) -> str:
    """
    Erzeugt einen Lizenzschlüssel für eine bestimmte Maschinen-ID.

    machine_id: die ID aus dem Lizenz-Tab des Kunden (get_machine_id)
    expires_on: Ablaufdatum im Format 'YYYY-MM-DD' oder None für unbegrenzt
    """
    mid = _normalize_machine_id(machine_id)

    if expires_on:
        # Wir speichern das als Klartext im Key, z.B. 2026-12-31
        expires_str = expires_on.strip()
    else:
        expires_str = "PERP"  # Perpetual (unbefristet)

    payload = _build_payload(mid, expires_str)
    sig = _sign_payload(payload)

    # Format des Keys:
    # EA-<Version>-<Expires>-<Signatur>
    key = f"EA-{LICENSE_VERSION}-{expires_str}-{sig}"
    return key


# -------------------------------------------------------------------
# LIZENZ VALIDIEREN (wird im Programm verwendet)
# -------------------------------------------------------------------

def validate_license_key(machine_id: str, license_key: str) -> Tuple[bool, str]:
    """
    Prüft, ob ein Lizenzschlüssel zur lokalen Maschinen-ID passt
    und ob das Ablaufdatum (falls gesetzt) noch gültig ist.

    Rückgabe:
        (True, "OK") oder (False, "Fehlermeldung")
    """
    machine_id = _normalize_machine_id(machine_id)
    key = license_key.strip().upper()

    if not key.startswith("EA-"):
        return False, "Ungültiges Lizenzformat (Prefix fehlt)."

    parts = key.split("-")
    if len(parts) < 4:
        return False, "Ungültiges Lizenzformat (zu wenige Teile)."

    _, version, expires_str, sig_part = parts[0], parts[1], parts[2], parts[3]

    if version != LICENSE_VERSION:
        return False, f"Unbekannte Lizenzversion: {version}."

    # Ablauf prüfen
    if expires_str != "PERP":
        exp_date = _parse_date_yyyy_mm_dd(expires_str)
        if exp_date is None:
            return False, f"Ungültiges Ablaufdatum im Lizenzschlüssel: {expires_str}."
        today = date.today()
        if exp_date < today:
            return False, f"Lizenz abgelaufen am {exp_date.isoformat()}."

    # Signatur prüfen
    payload = _build_payload(machine_id, expires_str)
    expected_sig = _sign_payload(payload)

    if sig_part != expected_sig:
        return False, "Lizenz passt nicht zu dieser Maschine."

    # Wenn alles passt:
    if expires_str == "PERP":
        return True, "Lizenz gültig (unbefristet)."
    else:
        return True, f"Lizenz gültig bis {expires_str}."


# -------------------------------------------------------------------
# LIZENZ SPEICHERN / LADEN (wird von main.py genutzt)
# -------------------------------------------------------------------

def save_license_key(path: Union[str, Path], license_key: str) -> None:
    """
    Speichert den Lizenzschlüssel in einer kleinen JSON-Datei:
        { "license_key": "..." }
    """
    p = Path(path)
    p.parent.mkdir(exist_ok=True, parents=True)
    data = {"license_key": license_key}
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_saved_license(path: Union[str, Path]) -> Optional[str]:
    """
    Lädt einen gespeicherten Lizenzschlüssel aus der JSON-Datei.
    Gibt None zurück, wenn es keine Datei gibt oder etwas schiefgeht.
    """
    p = Path(path)
    if not p.is_file():
        return None

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("license_key")
    except Exception:
        return None
