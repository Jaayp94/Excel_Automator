# ea_core/cleaning.py

import pandas as pd


def clean_dataframe(
    df: pd.DataFrame,
    remove_empty_rows: bool = True,
    duplicate_subset: str | list[str] | None = None
) -> pd.DataFrame:
    """
    Führt einfache Bereinigungsschritte aus:
    - optional: komplett leere Zeilen entfernen
    - optional: Duplikate anhand einer oder mehrerer Spalten entfernen
    """
    work = df.copy()

    if remove_empty_rows:
        work = work.dropna(how="all")

    if duplicate_subset:
        work = work.drop_duplicates(subset=duplicate_subset)
    return work


def remove_duplicates(df: pd.DataFrame, subset: str | list[str] | None = None) -> pd.DataFrame:
    """
    Ältere Hilfsfunktion – Wrapper um clean_dataframe ohne Leerzeilen-Entfernung.
    """
    return clean_dataframe(df, remove_empty_rows=False, duplicate_subset=subset)
