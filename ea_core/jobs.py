# ea_core/jobs.py

import json
from pathlib import Path


def save_job(config: dict, filepath: str) -> str:
    """
    Speichert eine Analyse-Konfiguration als JSON.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    return str(path)


def load_job(filepath: str) -> dict:
    """
    Lädt eine gespeicherte Job-Konfiguration.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(filepath)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
