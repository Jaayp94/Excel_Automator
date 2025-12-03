# ea_core/analysis.py

import pandas as pd
import logging

logger = logging.getLogger(__name__)


def basic_group_analysis(
    df: pd.DataFrame,
    group_cols: list[str],
    agg_col: str,
    agg_func: str = "sum"
) -> pd.DataFrame:
    """
    Gruppiert Daten nach 1–2 Spalten mit einer Aggregationsfunktion.
    """
    if not group_cols:
        raise ValueError("Mindestens eine Gruppierspalte erforderlich.")

    for gc in group_cols:
        if gc not in df.columns:
            raise KeyError(f"Gruppierspalte '{gc}' nicht im DataFrame.")

    if agg_col not in df.columns:
        raise KeyError(f"Aggregationsspalte '{agg_col}' nicht im DataFrame.")

    if agg_func not in {"sum", "mean", "count", "min", "max"}:
        raise ValueError(f"Unbekannte Funktion '{agg_func}'")

    work_df = df.copy()
    work_df[agg_col] = pd.to_numeric(work_df[agg_col], errors="coerce")

    work_df = work_df.dropna(subset=[agg_col])

    grouped = getattr(work_df.groupby(group_cols)[agg_col], agg_func)().reset_index()
    return grouped


def quick_column_insight(df: pd.DataFrame, col: str, max_rows: int = 25) -> pd.DataFrame:
    """
    Liefert eine 'Quick Analyse' pro Spalte.
    - numerisch → Top-Werte + relevante Kontextspalten
    - text → Value Counts alphabetisch
    """
    if col not in df.columns:
        raise KeyError(f"Spalte '{col}' nicht im DataFrame.")

    series = df[col]
    s_num = pd.to_numeric(series, errors="coerce")
    is_num = s_num.notna().sum() > 0

    if is_num:
        work = df.copy()
        work["_value_"] = s_num

        context = []
        for c in df.columns:
            if c == col:
                continue
            if any(
                k in c.lower()
                for k in ["kunde", "menge", "anzahl", "product", "ware"]
            ):
                context.append(c)

        if not context:
            context = [c for c in df.columns if c != col][:2]

        cols = context + [col]
        return work.sort_values("_value_", ascending=False)[cols].head(max_rows)

    else:
        vc = series.astype(str).value_counts().reset_index()
        vc.columns = [col, "Anzahl"]
        return vc.sort_values(col).head(max_rows)
