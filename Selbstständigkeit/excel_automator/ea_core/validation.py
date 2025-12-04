# ea_core/validation.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple

import pandas as pd


@dataclass
class ValidationResult:
    """Container für das Ergebnis einer Prüfung."""
    title: str
    message: str
    issues: Optional[pd.DataFrame] = None


# ---------------------------------------------------------
# Numerische Prüfung: B
# ---------------------------------------------------------

def validate_numeric_range(
    df: pd.DataFrame,
    column: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> ValidationResult:
    if column not in df.columns:
        return ValidationResult(
            title="Numerische Prüfung",
            message=f"Spalte '{column}' wurde nicht gefunden.",
            issues=None,
        )

    series = pd.to_numeric(df[column], errors="coerce")
    total = len(series)
    nan_count = series.isna().sum()

    mask = pd.Series(False, index=df.index)
    if min_value is not None:
        mask |= series < min_value
    if max_value is not None:
        mask |= series > max_value

    issues = df.loc[mask].copy()
    out_of_range = mask.sum()

    msg_lines = [
        f"Numerische Prüfung für Spalte: {column}",
        f"Gesamtzeilen: {total}",
        f"Nicht interpretierbar (NaN): {nan_count}",
    ]

    if min_value is not None:
        msg_lines.append(f"Minimaler erlaubter Wert: {min_value}")
    if max_value is not None:
        msg_lines.append(f"Maximaler erlaubter Wert: {max_value}")

    msg_lines.append(f"Zeilen außerhalb des Bereichs: {out_of_range}")

    if out_of_range > 0:
        msg_lines.append("Beispiele (max. 10 Zeilen):")
        msg_lines.append(issues.head(10).to_string())

    return ValidationResult(
        title="Numerische Prüfung",
        message="\n".join(msg_lines),
        issues=issues if not issues.empty else None,
    )


# ---------------------------------------------------------
# Datumsprüfung: C
# ---------------------------------------------------------

def _parse_date_safe(value: str) -> Optional[datetime]:
    if not value:
        return None

    # Versuche ein paar gängige Formate
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    # Fallback: pandas to_datetime
    try:
        return pd.to_datetime(value)
    except Exception:
        return None


def validate_date_range(
    df: pd.DataFrame,
    column: str,
    min_date_str: Optional[str] = None,
    max_date_str: Optional[str] = None,
) -> ValidationResult:
    if column not in df.columns:
        return ValidationResult(
            title="Datumsprüfung",
            message=f"Spalte '{column}' wurde nicht gefunden.",
            issues=None,
        )

    min_date = _parse_date_safe(min_date_str) if min_date_str else None
    max_date = _parse_date_safe(max_date_str) if max_date_str else None

    # pandas kümmert sich um die meisten Formate
    series = pd.to_datetime(df[column], errors="coerce", dayfirst=True)
    total = len(series)
    nan_count = series.isna().sum()

    mask = pd.Series(False, index=df.index)
    if min_date is not None:
        mask |= series < min_date
    if max_date is not None:
        mask |= series > max_date

    issues = df.loc[mask].copy()
    out_of_range = mask.sum()

    msg_lines = [
        f"Datumsprüfung für Spalte: {column}",
        f"Gesamtzeilen: {total}",
        f"Nicht interpretierbare Datumswerte (NaT): {nan_count}",
    ]

    if min_date is not None:
        msg_lines.append(f"Frühestes erlaubtes Datum: {min_date.date()}")
    if max_date is not None:
        msg_lines.append(f"Spätestes erlaubtes Datum: {max_date.date()}")

    msg_lines.append(f"Zeilen außerhalb des Bereichs: {out_of_range}")

    if out_of_range > 0:
        msg_lines.append("Beispiele (max. 10 Zeilen):")
        msg_lines.append(issues.head(10).to_string())

    return ValidationResult(
        title="Datumsprüfung",
        message="\n".join(msg_lines),
        issues=issues if not issues.empty else None,
    )


# ---------------------------------------------------------
# Text-Normalisierung: D
# ---------------------------------------------------------

def normalize_text_column(
    df: pd.DataFrame,
    column: str,
    mode: str = "upper_strip",
) -> Tuple[pd.DataFrame, ValidationResult]:
    """
    mode:
        - 'upper_strip' -> TRIM + UPPER
        - 'lower_strip' -> TRIM + lower
        - 'title_strip' -> TRIM + Title Case
    Erstellt eine neue Spalte '<column>_norm' und lässt die Originalspalte unverändert.
    """
    if column not in df.columns:
        return df, ValidationResult(
            title="Textnormalisierung",
            message=f"Spalte '{column}' wurde nicht gefunden.",
            issues=None,
        )

    new_df = df.copy()
    s = new_df[column].astype("string")

    norm = s.str.strip()

    if mode == "lower_strip":
        norm = norm.str.lower()
        mode_label = "Kleinschreibung (lower)"
    elif mode == "title_strip":
        norm = norm.str.title()
        mode_label = "Title Case"
    else:
        norm = norm.str.upper()
        mode_label = "Großschreibung (UPPER)"

    new_col = f"{column}_norm"
    new_df[new_col] = norm

    changed_mask = (s != norm) & ~(s.isna() & norm.isna())
    changed_rows = int(changed_mask.sum())

    msg_lines = [
        f"Textnormalisierung für Spalte: {column}",
        f"Neue Spalte: {new_col}",
        f"Modus: {mode_label}",
        f"Geänderte Zeilen: {changed_rows}",
    ]

    examples = new_df.loc[changed_mask, [column, new_col]].drop_duplicates().head(10)
    if not examples.empty:
        msg_lines.append("Beispiele geänderter Werte (max. 10 Zeilen):")
        msg_lines.append(examples.to_string(index=False))

    return new_df, ValidationResult(
        title="Textnormalisierung",
        message="\n".join(msg_lines),
        issues=examples if not examples.empty else None,
    )
