print(">>> DEBUG: Diese main.py wurde geladen")

IMPRINT_TEXT = (
    "Impressum"
    "------------------------------\n"
    "Softwareanbieter: Jean-Pascal Lohmann\n"
    "38154 Königslutter am Elm\n"
    "Telefon:017672122332\n"
    "+49 17672122332\n"
    "E-Mail:jean.lohmann@gmx.de\n"
    "Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV:\n"
    "Jean-Pascal Lohmann\n"
)


import json
import logging
from pathlib import Path

import PySimpleGUI as sg
import pandas as pd

from ea_core.io_functions import load_file, profile_dataframe
from ea_core.cleaning import clean_dataframe
from ea_core.merge import merge_dataframes
from ea_core.analysis import basic_group_analysis, quick_column_insight
from ea_core.exporting import export_to_excel
from ea_core.jobs import save_job, load_job
from ea_core.ppt_export import export_analysis_to_pptx
from ea_core.license import (
    get_machine_id,
    load_saved_license,
    save_license_key,
    validate_license_key,
)


# ------------------------- Logging & Config -------------------------

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
JOBS_DIR = BASE_DIR / "jobs"
LOGS_DIR = BASE_DIR / "logs"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LICENSE_FILE = CONFIG_DIR / "license.json"

CONFIG_DIR.mkdir(exist_ok=True)
JOBS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOGS_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger("excel_automator")

DEFAULT_SETTINGS = {
    "jobs_dir": "jobs",
    "logs_dir": "logs",
    "default_export_name": "ergebnis.xlsx"
}

# Settings laden (robust, falls settings.json leer/kaputt ist)
if SETTINGS_FILE.is_file():
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as f:
            SETTINGS = json.load(f)
    except Exception:
        SETTINGS = DEFAULT_SETTINGS
else:
    SETTINGS = DEFAULT_SETTINGS


# ------------------------- Globale Zustände -------------------------

current_df: pd.DataFrame | None = None
current_df_name: str = "Aktive Daten"

second_df: pd.DataFrame | None = None  # für Merge
merged_df: pd.DataFrame | None = None
analysis_df: pd.DataFrame | None = None
license_valid: bool = False
license_message: str = ""


# ------------------------- Hilfsfunktionen GUI -------------------------

def update_column_dropdowns(window: sg.Window):
    """
    Aktualisiert Dropdowns und Spaltenliste, die Spalten der aktiven Daten anzeigen.
    """
    global current_df
    cols = list(current_df.columns) if current_df is not None else []

    # Cleaning
    window["-CLEAN_DUP_COL-"].update(values=cols)

    # Merge (linke Spalte)
    window["-MERGE_LEFT_KEY-"].update(values=cols)

    # Analysis-Dropdowns
    window["-ANALYSIS_GROUP1-"].update(values=cols)
    window["-ANALYSIS_GROUP2-"].update(values=[""] + cols)
    window["-ANALYSIS_AGG_COL-"].update(values=cols)

    # Quick-Analyse Spaltenliste
    window["-ANALYSIS_COL_LIST-"].update(values=cols)


def update_merge_right_dropdown(window: sg.Window):
    """
    Aktualisiert Dropdown für rechte Merge-Spalte (second_df).
    """
    global second_df
    cols = list(second_df.columns) if second_df is not None else []
    window["-MERGE_RIGHT_KEY-"].update(values=cols)


def show_message(window: sg.Window, text: str):
    window["-STATUS-"].update(text)


# ------------------------- GUI Layout -------------------------

def make_layout():
    sg.theme("DarkBlue14")  # moderneres Theme

    # Header
    header_col = [
        [sg.Text("Excel Automator v0.2", font=("Segoe UI", 16, "bold"))],
        [sg.Text("Automatisierte Auswertung und Reports für CSV/Excel-Daten", font=("Segoe UI", 10))]
    ]

    header = [
        [sg.Column(header_col, pad=(10, 5))]
    ]

    # Tab 1: Import & Vorschau
    tab_import = [
        [sg.Text("Eingabedatei (CSV/Excel):", font=("Segoe UI", 10, "bold"))],
        [
            sg.Input(key="-IMPORT_FILE-"),
            sg.FileBrowse("Durchsuchen", file_types=(("CSV/Excel", "*.csv;*.xlsx;*.xls"),))
        ],
        [sg.Button("Datei laden", key="-BTN_LOAD-", button_color=("white", "#007ACC"))],
        [sg.Frame("Datenprofil", [[sg.Multiline(size=(100, 20), key="-IMPORT_INFO-")]], pad=(0, 10))]
    ]

    # Tab 2: Bereinigung
    tab_clean = [
        [sg.Text("Bereinigung der aktiven Daten", font=("Segoe UI", 10, "bold"))],
        [sg.Checkbox("Leere Zeilen entfernen", default=True, key="-CLEAN_EMPTY-")],
        [
            sg.Text("Duplikate entfernen anhand Spalte:"),
            sg.Combo([], key="-CLEAN_DUP_COL-", size=(30, 1))
        ],
        [sg.Button("Bereinigung ausführen", key="-BTN_CLEAN-", button_color=("white", "#007ACC"))],
        [sg.Frame("Bereinigungsprotokoll", [[sg.Multiline(size=(100, 10), key="-CLEAN_INFO-")]], pad=(0, 10))]
    ]

    # Tab 3: Merge
    tab_merge = [
        [sg.Text("Zweite Datei für Merge auswählen (CSV/Excel):", font=("Segoe UI", 10, "bold"))],
        [
            sg.Input(key="-MERGE_FILE-"),
            sg.FileBrowse("Durchsuchen", file_types=(("CSV/Excel", "*.csv;*.xlsx;*.xls"),))
        ],
        [sg.Button("Zweite Datei laden", key="-BTN_LOAD_SECOND-", button_color=("white", "#007ACC"))],
        [sg.HorizontalSeparator()],
        [sg.Text("Merge-Konfiguration:", font=("Segoe UI", 10, "bold"))],
        [
            sg.Text("Schlüssel links (aktive Daten):", size=(28, 1)),
            sg.Combo([], key="-MERGE_LEFT_KEY-", size=(30, 1))
        ],
        [
            sg.Text("Schlüssel rechts (zweite Datei):", size=(28, 1)),
            sg.Combo([], key="-MERGE_RIGHT_KEY-", size=(30, 1))
        ],
        [
            sg.Text("Merge-Typ:", size=(28, 1)),
            sg.Combo(["inner", "left", "right", "outer"], default_value="inner", key="-MERGE_HOW-", size=(10, 1))
        ],
        [sg.Button("Merge ausführen", key="-BTN_MERGE-", button_color=("white", "#007ACC"))],
        [sg.Frame("Merge-Ergebnis", [[sg.Multiline(size=(100, 10), key="-MERGE_INFO-")]], pad=(0, 10))]
    ]

    # Tab 4: Analyse
    tab_analysis = [
        [sg.Text("Analyse & Quick-Filter", font=("Segoe UI", 10, "bold"))],
        [
            sg.Column(
                [
                    [
                        sg.Text("Gruppierspalte 1:", size=(20, 1)),
                        sg.Combo([], key="-ANALYSIS_GROUP1-", size=(30, 1))
                    ],
                    [
                        sg.Text("Gruppierspalte 2 (optional):", size=(20, 1)),
                        sg.Combo([], key="-ANALYSIS_GROUP2-", size=(30, 1))
                    ],
                    [
                        sg.Text("Aggregationsspalte (numerisch):", size=(20, 1)),
                        sg.Combo([], key="-ANALYSIS_AGG_COL-", size=(30, 1))
                    ],
                    [
                        sg.Text("Funktion:", size=(20, 1)),
                        sg.Combo(
                            ["sum", "mean", "count", "min", "max"],
                            default_value="sum",
                            key="-ANALYSIS_FUNC-",
                            size=(10, 1)
                        )
                    ],
                    [
                        sg.Button(
                            "Analyse ausführen",
                            key="-BTN_ANALYSIS-",
                            button_color=("white", "#007ACC")
                        )
                    ],
                ],
                vertical_alignment="top",
                expand_x=True,
            ),
            sg.VSeparator(),
            sg.Column(
                [
                    [sg.Text("Schnellauswahl Spalten", font=("Segoe UI", 10, "bold"))],
                    [
                        sg.Listbox(
                            values=[],
                            size=(25, 15),
                            key="-ANALYSIS_COL_LIST-",
                            enable_events=True
                        )
                    ],
                    [sg.Text("Tipp: Spalte anklicken für Quick-Analyse.", font=("Segoe UI", 8))]
                ],
                vertical_alignment="top",
                pad=(10, 0),
            )
        ],
        [
            sg.Frame(
                "Analyse-Ergebnis",
                [
                    [
                        sg.Multiline(
                            size=(110, 20),
                            key="-ANALYSIS_INFO-",
                            font=("Consolas", 9),
                            autoscroll=True
                        )
                    ]
                ],
                pad=(0, 10),
                expand_x=True,
                expand_y=True,
            )
        ],
    ]

    # Tab 5: Export
    tab_export = [
        [sg.Text("Export aktiver Daten / Analyse nach Excel", font=("Segoe UI", 10, "bold"))],
        [
            sg.Text("Zieldatei:", size=(10, 1)),
            sg.Input(str(BASE_DIR / SETTINGS.get("default_export_name", "ergebnis.xlsx")), key="-EXPORT_FILE-"),
            sg.FileSaveAs("Ziel wählen", file_types=(("Excel", "*.xlsx"),))
        ],
        [sg.Checkbox("Aktive Daten exportieren", default=True, key="-EXPORT_MAIN-")],
        [sg.Checkbox("Analyse-Ergebnis exportieren (falls vorhanden)", default=True, key="-EXPORT_ANALYSIS-")],
        [sg.Button("Export starten", key="-BTN_EXPORT-", button_color=("white", "#007ACC"))],
        [sg.Frame("Export-Protokoll", [[sg.Multiline(size=(100, 10), key="-EXPORT_INFO-")]], pad=(0, 10))]
    ]

    # Tab 6: Jobs
    tab_jobs = [
        [sg.Text("Einfache Job-Konfiguration (Import + Bereinigung + Export)", font=("Segoe UI", 10, "bold"))],
        [sg.Text("Job-Name:"), sg.Input(key="-JOB_NAME-")],
        [
            sg.Text("Eingabedatei:", size=(10, 1)),
            sg.Input(key="-JOB_IN-"),
            sg.FileBrowse("Durchsuchen", file_types=(("CSV/Excel", "*.csv;*.xlsx;*.xls"),))
        ],
        [
            sg.Text("Ausgabedatei:", size=(10, 1)),
            sg.Input(key="-JOB_OUT-"),
            sg.FileSaveAs("Ziel wählen", file_types=(("Excel", "*.xlsx"),))
        ],
        [sg.Checkbox("Leere Zeilen entfernen", default=True, key="-JOB_CLEAN_EMPTY-")],
        [sg.Text("Duplikate anhand Spalte:"), sg.Input(key="-JOB_DUP_COL-")],
        [
            sg.Button("Job speichern", key="-BTN_JOB_SAVE-", button_color=("white", "#007ACC")),
            sg.Text("oder Job-Datei laden & ausführen:"),
            sg.Input(key="-JOB_FILE-"),
            sg.FileBrowse("Job auswählen", file_types=(("Job-Datei", "*.json"),)),
            sg.Button("Job ausführen", key="-BTN_JOB_RUN-", button_color=("white", "#007ACC"))
        ],
        [sg.Frame("Job-Protokoll", [[sg.Multiline(size=(100, 10), key="-JOB_INFO-")]], pad=(0, 10))]
    ]

    # Tab 7: PPTX-Export
    tab_ppt = [
        [sg.Text("PowerPoint-Report aus aktueller Analyse", font=("Segoe UI", 10, "bold"))],
        [
            sg.Text("Zieldatei (.pptx):", size=(15, 1)),
            sg.Input(str(BASE_DIR / "report_auswertung.pptx"), key="-PPTX_FILE-"),
            sg.FileSaveAs("Ziel wählen", file_types=(("PowerPoint", "*.pptx"),))
        ],
        [
            sg.Text("Titel:", size=(15, 1)),
            sg.Input("Automatisierter Auswertungsreport", key="-PPTX_TITLE-")
        ],
        [
            sg.Text("Untertitel:", size=(15, 1)),
            sg.Input("Erstellt mit Excel Automator", key="-PPTX_SUBTITLE-")
        ],
        [sg.Button("PPTX-Report erstellen", key="-BTN_PPTX_EXPORT-", button_color=("white", "#007ACC"))],
        [sg.Frame("PPTX-Protokoll", [[sg.Multiline(size=(100, 10), key="-PPTX_INFO-")]], pad=(0, 10))]
    ]

    # Tab 8: Lizenz
    machine_id = get_machine_id()
    tab_license = [
        [sg.Text("Lizenzverwaltung", font=("Segoe UI", 10, "bold"))],
        [
            sg.Text("Maschinen-ID:", size=(12, 1)),
            sg.Input(machine_id, key="-LIC_MACHINE-", size=(40, 1), disabled=True),
            sg.Text("← Diese ID an dich schicken, um einen Lizenzschlüssel zu erhalten.")
        ],
        [
            sg.Text("Lizenzschlüssel:", size=(12, 1)),
            sg.Input(key="-LIC_KEY-", size=(40, 1)),
            sg.Button("Lizenz prüfen & speichern", key="-BTN_LIC_SAVE-", button_color=("white", "#007ACC")),
        ],
        [
            sg.Text("Lizenzstatus:", font=("Segoe UI", 10, "bold")),
        ],
        [
            sg.Multiline(size=(100, 4), key="-LIC_STATUS-", disabled=True)
        ],
    ]
      # Tab 9: Impressum
    tab_imprint = [
        [sg.Text("Impressum", font=("Segoe UI", 12, "bold"))],
        [
            sg.Multiline(
                IMPRINT_TEXT,
                size=(100, 12),
                disabled=True,
                key="-IMPRINT_TEXT-"
            )
        ]
    ]

    tabs = [
        sg.Tab("Import", tab_import),
        sg.Tab("Bereinigung", tab_clean),
        sg.Tab("Merge", tab_merge),
        sg.Tab("Analyse", tab_analysis),
        sg.Tab("Export", tab_export),
        sg.Tab("Jobs", tab_jobs),
        sg.Tab("PPTX-Export", tab_ppt),
        sg.Tab("Lizenz", tab_license),
        sg.Tab("Impressum", tab_imprint),
    ]

    layout = [
        *header,
        [sg.TabGroup([tabs], expand_x=True, expand_y=True)],
        [sg.HorizontalSeparator()],
        [sg.Text("Status:", font=("Segoe UI", 10, "bold")), sg.Text("", key="-STATUS-", size=(80, 1))]
    ]

    return layout


# ------------------------- main() -------------------------

def main():
    global current_df, current_df_name, second_df, merged_df, analysis_df, license_valid, license_message

    window = sg.Window("Excel Automator v0.2", make_layout(), resizable=True, finalize=True)

    # Lizenz beim Start prüfen
    machine_id = get_machine_id()
    saved_key = load_saved_license(LICENSE_FILE)
    if saved_key:
        ok, msg = validate_license_key(machine_id, saved_key)
        license_valid = ok
        license_message = msg
    else:
        license_valid = False
        license_message = "Keine Lizenz gefunden. Bitte Lizenzschlüssel eingeben."

    window["-LIC_STATUS-"].update(license_message)
    if not license_valid:
        show_message(window, "Keine gültige Lizenz. Einige Funktionen sind eingeschränkt.")
    else:
        show_message(window, "Lizenz gültig. Voller Funktionsumfang verfügbar.")

    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED:
            break

        # --------------- Lizenz speichern/prüfen ---------------
        if event == "-BTN_LIC_SAVE-":
            key = values["-LIC_KEY-"].strip()
            if not key:
                window["-LIC_STATUS-"].update("Bitte einen Lizenzschlüssel eingeben.")
                show_message(window, "Kein Lizenzschlüssel eingegeben.")
            else:
                ok, msg = validate_license_key(machine_id, key)
                license_valid = ok
                license_message = msg
                window["-LIC_STATUS-"].update(msg)
                if ok:
                    save_license_key(LICENSE_FILE, key)
                    show_message(window, "Lizenz gültig und gespeichert.")
                else:
                    show_message(window, "Lizenz ungültig. Bitte prüfen.")

        # --------------- Import ---------------

        if event == "-BTN_LOAD-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Import ist gesperrt.")
                continue

            filepath = values["-IMPORT_FILE-"]
            if not filepath:
                show_message(window, "Bitte zuerst eine Datei auswählen.")
                continue
            try:
                current_df = load_file(filepath)
                current_df_name = Path(filepath).name
                txt = profile_dataframe(current_df, current_df_name)
                window["-IMPORT_INFO-"].update(txt)
                show_message(window, f"Datei geladen: {current_df_name}")
                update_column_dropdowns(window)
            except Exception as e:
                logger.exception("Fehler beim Laden der Datei.")
                window["-IMPORT_INFO-"].update(f"Fehler beim Laden:\n{e}")
                show_message(window, "Fehler beim Laden der Datei. Details im Log.")

        # --------------- Cleaning ---------------

        if event == "-BTN_CLEAN-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Bereinigung ist gesperrt.")
                continue

            if current_df is None:
                show_message(window, "Keine aktiven Daten vorhanden. Bitte zuerst Datei laden.")
                continue

            remove_empty = values["-CLEAN_EMPTY-"]
            dup_col = values["-CLEAN_DUP_COL-"] or None

            try:
                before_rows = len(current_df)
                current_df = clean_dataframe(current_df, remove_empty_rows=remove_empty, duplicate_subset=dup_col)
                after_rows = len(current_df)
                txt = f"Bereinigung abgeschlossen.\nZeilen vorher: {before_rows}\nZeilen nachher: {after_rows}"
                window["-CLEAN_INFO-"].update(txt)
                show_message(window, "Bereinigung erfolgreich.")
                window["-IMPORT_INFO-"].update(profile_dataframe(current_df, current_df_name))
                update_column_dropdowns(window)
            except Exception as e:
                logger.exception("Fehler bei Bereinigung.")
                window["-CLEAN_INFO-"].update(f"Fehler bei Bereinigung:\n{e}")
                show_message(window, "Fehler bei Bereinigung. Details im Log.")

        # --------------- Merge ---------------

        if event == "-BTN_LOAD_SECOND-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Merge-Funktionen sind gesperrt.")
                continue

            filepath = values["-MERGE_FILE-"]
            if not filepath:
                show_message(window, "Bitte zweite Datei auswählen.")
                continue
            try:
                second_df = load_file(filepath)
                window["-MERGE_INFO-"].update(
                    "Zweite Datei geladen:\n" + profile_dataframe(second_df, Path(filepath).name)
                )
                show_message(window, f"Zweite Datei geladen: {Path(filepath).name}")
                update_merge_right_dropdown(window)
            except Exception as e:
                logger.exception("Fehler beim Laden der zweiten Datei.")
                window["-MERGE_INFO-"].update(f"Fehler beim Laden der zweiten Datei:\n{e}")
                show_message(window, "Fehler beim Laden der zweiten Datei. Details im Log.")

        if event == "-BTN_MERGE-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Merge-Funktionen sind gesperrt.")
                continue

            if current_df is None or second_df is None:
                show_message(window, "Für Merge werden aktive Daten und zweite Datei benötigt.")
                continue

            left_key = values["-MERGE_LEFT_KEY-"]
            right_key = values["-MERGE_RIGHT_KEY-"]
            how = values["-MERGE_HOW-"] or "inner"

            if not left_key or not right_key:
                show_message(window, "Bitte beide Schlüsselspalten auswählen.")
                continue

            try:
                merged_df = merge_dataframes(current_df, second_df, left_key, right_key, how=how)
                current_df = merged_df
                current_df_name = f"Merge({current_df_name})"
                window["-MERGE_INFO-"].update(
                    "Merge erfolgreich.\n" + profile_dataframe(current_df, current_df_name)
                )
                show_message(window, "Merge erfolgreich.")
                window["-IMPORT_INFO-"].update(profile_dataframe(current_df, current_df_name))
                update_column_dropdowns(window)
            except Exception as e:
                logger.exception("Fehler beim Merge.")
                window["-MERGE_INFO-"].update(f"Fehler beim Merge:\n{e}")
                show_message(window, "Fehler beim Merge. Details im Log.")

        # --------------- Quick-Analyse per Spaltenklick ---------------

        if event == "-ANALYSIS_COL_LIST-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Analyse ist gesperrt.")
                continue

            if current_df is None:
                show_message(window, "Keine aktiven Daten vorhanden.")
                continue

            selected_cols = values["-ANALYSIS_COL_LIST-"]
            if not selected_cols:
                continue

            col = selected_cols[0]

            try:
                quick_df = quick_column_insight(current_df, col)
                analysis_df = quick_df
                preview = quick_df.to_string()
                window["-ANALYSIS_INFO-"].update(
                    f"Schnell-Analyse für Spalte: {col}\n\n" + preview
                )
                show_message(window, f"Schnell-Analyse für '{col}' erstellt.")
            except Exception as e:
                logger.exception("Fehler bei Quick-Analyse.")
                window["-ANALYSIS_INFO-"].update(f"Fehler bei Quick-Analyse:\n{e}")
                show_message(window, "Fehler bei Quick-Analyse. Details im Log.")

        # --------------- Analyse ---------------

        if event == "-BTN_ANALYSIS-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Analyse ist gesperrt.")
                continue

            if current_df is None:
                show_message(window, "Keine aktiven Daten vorhanden.")
                continue

            group1 = values["-ANALYSIS_GROUP1-"]
            group2 = values["-ANALYSIS_GROUP2-"]
            agg_col = values["-ANALYSIS_AGG_COL-"]
            func = values["-ANALYSIS_FUNC-"] or "sum"

            group_cols = [c for c in [group1, group2] if c]

            if not group_cols or not agg_col:
                show_message(window, "Bitte mindestens eine Gruppierspalte und eine Aggregationsspalte wählen.")
                continue

            try:
                analysis_df = basic_group_analysis(current_df, group_cols, agg_col, agg_func=func)
                preview = analysis_df.head(50).to_string()
                window["-ANALYSIS_INFO-"].update(
                    "Analyse erfolgreich.\n" + preview
                )
                show_message(window, "Analyse erfolgreich.")
            except Exception as e:
                logger.exception("Fehler bei Analyse.")
                window["-ANALYSIS_INFO-"].update(f"Fehler bei Analyse:\n{e}")
                show_message(window, "Fehler bei Analyse. Details im Log.")

        # --------------- Export ---------------

        if event == "-BTN_EXPORT-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Export ist gesperrt.")
                continue

            export_path = values["-EXPORT_FILE-"]
            if not export_path:
                show_message(window, "Bitte Exportdatei wählen.")
                continue

            export_main = values["-EXPORT_MAIN-"]
            export_analysis_flag = values["-EXPORT_ANALYSIS-"]

            if not export_main and not export_analysis_flag:
                show_message(window, "Bitte mindestens einen Export auswählen.")
                continue

            main_df_to_export = current_df if export_main and current_df is not None else None
            analysis_to_export = analysis_df if export_analysis_flag and analysis_df is not None else None

            if main_df_to_export is None and analysis_to_export is None:
                show_message(window, "Keine Daten zum Export verfügbar.")
                continue

            try:
                export_to_excel(export_path, main_df_to_export, analysis_to_export)
                window["-EXPORT_INFO-"].update(f"Export erfolgreich nach:\n{export_path}")
                show_message(window, "Export erfolgreich.")
            except Exception as e:
                logger.exception("Fehler beim Export.")
                window["-EXPORT_INFO-"].update(f"Fehler beim Export:\n{e}")
                show_message(window, "Fehler beim Export. Details im Log.")

        # --------------- Jobs ---------------

        if event == "-BTN_JOB_SAVE-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Jobs sind gesperrt.")
                continue

            name = values["-JOB_NAME-"].strip()
            job_in = values["-JOB_IN-"].strip()
            job_out = values["-JOB_OUT-"].strip()
            clean_empty = values["-JOB_CLEAN_EMPTY-"]
            dup_col = values["-JOB_DUP_COL-"].strip() or None

            if not name or not job_in or not job_out:
                show_message(window, "Job-Name, Eingabe- und Ausgabedatei werden benötigt.")
                continue

            job_config = {
                "name": name,
                "input": job_in,
                "output": job_out,
                "clean_empty": clean_empty,
                "dup_col": dup_col
            }

            job_file = JOBS_DIR / f"{name}.json"
            try:
                save_job(job_config, str(job_file))
                window["-JOB_INFO-"].update(f"Job gespeichert unter:\n{job_file}")
                show_message(window, "Job gespeichert.")
            except Exception as e:
                logger.exception("Fehler beim Speichern des Jobs.")
                window["-JOB_INFO-"].update(f"Fehler beim Speichern des Jobs:\n{e}")
                show_message(window, "Fehler beim Speichern des Jobs. Details im Log.")

        if event == "-BTN_JOB_RUN-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. Jobs sind gesperrt.")
                continue

            job_file = values["-JOB_FILE-"].strip()
            if not job_file:
                show_message(window, "Bitte eine Job-Datei auswählen.")
                continue

            try:
                job_config = load_job(job_file)
                job_in = job_config["input"]
                job_out = job_config["output"]
                clean_empty = job_config.get("clean_empty", True)
                dup_col = job_config.get("dup_col", None)

                df = load_file(job_in)
                df = clean_dataframe(df, remove_empty_rows=clean_empty, duplicate_subset=dup_col)
                export_to_excel(job_out, df, None)

                window["-JOB_INFO-"].update(
                    f"Job erfolgreich ausgeführt.\nEingabe: {job_in}\nAusgabe: {job_out}"
                )
                show_message(window, "Job erfolgreich ausgeführt.")
            except Exception as e:
                logger.exception("Fehler beim Ausführen des Jobs.")
                window["-JOB_INFO-"].update(f"Fehler beim Job:\n{e}")
                show_message(window, "Fehler beim Job. Details im Log.")

        # --------------- PPTX-Export ---------------

        if event == "-BTN_PPTX_EXPORT-":
            if not license_valid:
                show_message(window, "Keine gültige Lizenz. PPTX-Export ist gesperrt.")
                continue

            if analysis_df is None or analysis_df.empty:
                show_message(window, "Keine Analyse-Daten vorhanden. Bitte zuerst eine Analyse ausführen.")
                window["-PPTX_INFO-"].update("Keine Analyse-Daten vorhanden.\nBitte zuerst im Tab 'Analyse' eine Auswertung erstellen.")
                continue

            pptx_path = values["-PPTX_FILE-"].strip()
            title = values["-PPTX_TITLE-"].strip() or "Automatisierter Auswertungsreport"
            subtitle = values["-PPTX_SUBTITLE-"].strip() or "Erstellt mit Excel Automator"

            if not pptx_path:
                show_message(window, "Bitte eine Zieldatei für den PowerPoint-Export angeben.")
                continue

            try:
                out_path = export_analysis_to_pptx(pptx_path, analysis_df, title=title, subtitle=subtitle)
                window["-PPTX_INFO-"].update(f"PPTX-Report erfolgreich erstellt:\n{out_path}")
                show_message(window, "PPTX-Report erfolgreich erstellt.")
            except Exception as e:
                logger.exception("Fehler beim PowerPoint-Export.")
                window["-PPTX_INFO-"].update(f"Fehler beim PowerPoint-Export:\n{e}")
                show_message(window, "Fehler beim PowerPoint-Export. Details im Log.")

    window.close()


if __name__ == "__main__":
    print("Starte Excel Automator v0.2...")
    main()
    print("Programm beendet.")
