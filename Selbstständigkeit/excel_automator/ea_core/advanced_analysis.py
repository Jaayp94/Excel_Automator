import pandas as pd
import numpy as np

def detect_datetime_columns(df: pd.DataFrame):
    """
    Findet automatisch Spalten, die wie Datum/Zeit aussehen.
    """
    date_cols = []
    for col in df.columns:
        try:
            if df[col].dtype == "datetime64[ns]":
                date_cols.append(col)
            else:
                test = pd.to_datetime(df[col], errors="raise")
                date_cols.append(col)
        except:
            pass
    return date_cols


def generate_top_lists(df: pd.DataFrame, top_n=10):
    """
    Erstellt automatisch Top 10 Listen für alle nicht-numerischen Kategorien
    und zählt deren Häufigkeit.
    """
    results = {}

    for col in df.columns:
        if df[col].dtype == "object" or df[col].dtype == "string":
            vc = df[col].value_counts().head(top_n)
            if len(vc) > 0:
                results[col] = vc

    return results


def generate_kpis(df: pd.DataFrame):
    """
    Liefert Standard-Kennzahlen der Tabelle.
    """
    kpis = {}

    kpis["Zeilen gesamt"] = len(df)
    kpis["Spalten gesamt"] = len(df.columns)

    for col in df.columns:
        try:
            kpis[f"{col} – eindeutige Werte"] = df[col].nunique()
        except:
            pass

    # Numerische Kennzahlen
    numeric = df.select_dtypes(include=[np.number])

    if not numeric.empty:
        kpis["Numerische Spalten"] = list(numeric.columns)
        kpis["Gesamtsumme (numerisch)"] = numeric.sum().sum()
        kpis["Durchschnitt (numerisch)"] = numeric.mean().mean()

    return kpis


def time_series_analysis(df: pd.DataFrame):
    """
    Erkennt Datumsspalten und erstellt Zeitreihenanalysen.
    """
    date_cols = detect_datetime_columns(df)
    results = {}

    for col in date_cols:
        try:
            dates = pd.to_datetime(df[col], errors="coerce").dropna()

            results[col] = {
                "Pro Tag": dates.dt.date.value_counts().sort_index(),
                "Pro Woche": dates.dt.to_period("W").value_counts().sort_index(),
                "Pro Monat": dates.dt.to_period("M").value_counts().sort_index()
            }

        except:
            continue

    return results


def quick_insights(df: pd.DataFrame):
    """
    Erkennt Ausreißer, häufige Werte, Korrelationen.
    Kleine „Mini-KI“ ohne API.
    """
    insights = []

    # Höchste Varianz = wichtigste Spalten
    numeric = df.select_dtypes(include=[np.number])
    if not numeric.empty:
        var = numeric.var().sort_values(ascending=False)
        insights.append("Wichtigste numerische Spalten (höchste Varianz):")
        insights.append(str(var.head(5)))
        insights.append("")

    # Häufigste Werte
    for col in df.columns:
        try:
            vc = df[col].value_counts().head(3)
            insights.append(f"Häufigste Werte in {col}:")
            insights.append(str(vc))
            insights.append("")
        except:
            pass

    # Ausreißer
    if not numeric.empty:
        desc = numeric.describe()
        for col in numeric.columns:
            high = desc.at["75%", col] + 1.5 * (desc.at["75%", col] - desc.at["25%", col])
            low = desc.at["25%", col] - 1.5 * (desc.at["75%", col] - desc.at["25%", col])
            insights.append(f"Ausreißer in {col}: Werte < {low:.2f} oder > {high:.2f}")
        insights.append("")

    return "\n".join(insights)
