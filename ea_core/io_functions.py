# ea_core/io_functions.py

import pandas as pd
from pathlib import Path


def load_file(filepath: str) -> pd.DataFrame:
    """
    Lädt eine CSV- oder Excel-Datei ein.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")

    if path.suffix.lower() in [".csv", ".txt"]:
        df = pd.read_csv(path)
    elif path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Nicht unterstützter Dateityp: {path.suffix}")

    return df


def profile_df(df: pd.DataFrame, name: str = "Daten") -> str:
    """
    Textübersicht der geladenen Daten.
    """
    lines = []
    lines.append(f"Name: {name}")
    lines.append(f"Form: {df.shape[0]} Zeilen, {df.shape[1]} Spalten")
    lines.append("Spalten:")

    for col in df.columns:
        try:
            sample = df[col].dropna().iloc[0]
        except Exception:
            sample = "leer"

        lines.append(f"  - {col} (Beispiel: {repr(sample)})")

    return "\n".join(lines)


def profile_dataframe(df: pd.DataFrame, name: str = "Daten") -> str:
    """
    Alias für profile_df, damit main.py mit beiden Namen funktioniert.
    """
    return profile_df(df, name=name)
