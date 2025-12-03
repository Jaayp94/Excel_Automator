# ea_core/exporting.py

import pandas as pd
from pathlib import Path


def export_to_excel(df: pd.DataFrame, filepath: str) -> str:
    """
    Exportiert einen DataFrame als Excel-Datei.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    df.to_excel(path, index=False)
    return str(path)
