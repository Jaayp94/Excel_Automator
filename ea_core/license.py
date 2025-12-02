# ea_core/license.py

import hmac
import hashlib
import uuid
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Tuple


# Geheimer Schlüssel für die Lizenzsignatur
# (In echt: schön zufällig lassen und NICHT rumgeben)
_SECRET = b"ExcelAutomator-Lizenz-Secret-2025"
_PREFIX = "EA1"  # Produkt-Kennung, z.B. Excel Automator v1


def get_machine_id() -> str:
    """
    Gibt eine einfache Maschinen-ID zurück (basierend auf MAC-Adresse).
    Wird für die Lizenzbindung verwendet.
    """
    mac = uuid.getnode()
    return f"{mac:012X}"  # 12-stellig, HEX, z.B. 'A1B2C3D4E5F6'


def _build_signature(machine_id: str, expiry_str: str) -> str:
    """
    Erzeugt eine HMAC-Signatur aus Maschinen-ID und Ablaufdatum (YYYYMMDD).
    """
    msg = f"{machine_id}|{expiry_str}".encode("utf-8")
    sig = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest().upper()
    return sig[:8]  # auf 8 Zeichen kürzen


def _parse_license_key(license_key: str) -> Tuple[str, str]:
    """
    Erwartetes Format: EA1-YYYYMMDD-XXXXXXXX
    Rückgabe: (expiry_str, signature)
    """
    key = license_key.strip().upper().replace(" ", "")
    parts = key.split("-")
    if len(parts) != 3:
        raise ValueError("Ungültiges Lizenzformat.")
    prefix, expiry_str, sig = parts
    if prefix != _PREFIX:
        raise ValueError("Falsches Produktpräfix.")
    if len(expiry_str) != 8 or not expiry_str.isdigit():
        raise ValueError("Ungültiges Ablaufdatum im Lizenzschlüssel.")
    if len(sig) < 4:
        raise ValueError("Signatur zu kurz.")
    return expiry_str, sig


def validate_license_key(machine_id: str, license_key: str, today: date | None = None) -> Tuple[bool, str]:
    """
    Prüft, ob ein Lizenzschlüssel für diese Maschine gültig ist.
    - Format
    - Signatur
    - Ablaufdatum

    Rückgabe: (is_valid, nachricht)
    """
    if today is None:
        today = date.today()

    try:
        expiry_str, sig = _parse_license_key(license_key)
        expected_sig = _build_signature(machine_id, expiry_str)

        if sig != expected_sig:
            return False, "Lizenz ungültig: Signatur stimmt nicht."

        expiry_date = datetime.strptime(expiry_str, "%Y%m%d").date()
        if today > expiry_date:
            return False, f"Lizenz abgelaufen am {expiry_date.isoformat()}."

        return True, f"Lizenz gültig bis {expiry_date.isoformat()}."
    except Exception as e:
        return False, f"Lizenz ungültig: {e}"


def get_expiry_from_key(machine_id: str, license_key: str) -> date | None:
    """
    Liefert das Ablaufdatum aus einem Lizenzschlüssel, sofern gültig.
    """
    ok, msg = validate_license_key(machine_id, license_key)
    if not ok:
        return None
    expiry_str, _ = _parse_license_key(license_key)
    return datetime.strptime(expiry_str, "%Y%m%d").date()


def save_license_key(path: Path, license_key: str) -> None:
    """
    Speichert den Lizenzschlüssel in eine JSON-Datei.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"license_key": license_key}
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_saved_license(path: Path) -> str | None:
    """
    Lädt einen gespeicherten Lizenzschlüssel, falls vorhanden.
    """
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("license_key")
    except Exception:
        return None


# --- Hilfsfunktion: Lizenzschlüssel erzeugen (für dich als „Hersteller“) ---


def generate_license_key_for_machine(machine_id: str, valid_days: int = 365) -> str:
    """
    Erzeugt einen Lizenzschlüssel für eine bestimmte Maschine und Laufzeit.
    Diese Funktion brauchst nur du, um Keys zu generieren – nicht der Kunde.
    """
    expiry_date = date.today() + timedelta(days=valid_days)
    expiry_str = expiry_date.strftime("%Y%m%d")
    sig = _build_signature(machine_id, expiry_str)
    return f"{_PREFIX}-{expiry_str}-{sig}"
