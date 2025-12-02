# ea_core/merge.py

import pandas as pd


def merge_dataframes(df_left: pd.DataFrame, df_right: pd.DataFrame, key: str) -> pd.DataFrame:
    """
    Führt zwei DataFrames basierend auf einem Schlüssel zusammen (inner merge).
    """
    if key not in df_left.columns:
        raise KeyError(f"Spalte '{key}' nicht in linkem DataFrame")

    if key not in df_right.columns:
        raise KeyError(f"Spalte '{key}' nicht in rechtem DataFrame")

    return pd.merge(df_left, df_right, on=key, how="inner")
