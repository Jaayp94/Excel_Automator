print(">>> DEBUG: Diese main.py wurde geladen")

import json
import logging
from pathlib import Path

import PySimpleGUI as sg
import pandas as pd

# ------------------ Farben & UI ------------------
COLOR_BG = "#F4F6FA"
COLOR_CARD = "#FFFFFF"
COLOR_PRIMARY = "#1C7ED6"
COLOR_PRIMARY_HOVER = "#1971C2"
COLOR_TEXT = "#1F1F1F"

sg.theme("SystemDefault1")
sg.set_options(font=("Segoe UI", 10))

# ------------------ Impressum ------------------
IMPRINT_TEXT = (
    "Impressum\n"
    "------------------------------\n"
    "Softwareanbieter: Jean-Pascal Lohmann\n"
    "38154 Königslutter am Elm\n"
    "Telefon: 017672122332\n"
    "E-Mail: jean.lohmann@gmx.de\n"
    "Verantwortlich nach § 18 Abs. 2 MStV:\n"
    "Jean-Pascal Lohmann\n"
)

# ------------------ Module laden ------------------
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
from ea_core.validation import (
    validate_numeric_range,
    validate_date_range,
    normalize_text_column,
)


# OPTIONAL: Falls Modul existiert
try:
    from ea_core.advanced_analysis import (
        generate_top_lists,
        generate_kpis,
        time_series_analysis,
        quick_insights,
    )
    ADVANCED_AVAILABLE = True
except Exception:
    ADVANCED_AVAILABLE = False

# ------------------ Logging ------------------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

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

# Settings laden
if SETTINGS_FILE.exists():
    try:
        SETTINGS = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        SETTINGS = DEFAULT_SETTINGS
else:
    SETTINGS = DEFAULT_SETTINGS

# ------------------ Globale Variablen ------------------
current_df = None
current_df_name = ""
second_df = None
merged_df = None
analysis_df = None

license_valid = False
license_message = ""


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def update_column_dropdowns(window):
    if current_df is None:
        cols = []
    else:
        cols = list(current_df.columns)
    #Cleaning
    window["-CLEAN_DUP_COL-"].update(values=cols)
    #Merge
    window["-MERGE_LEFT_KEY-"].update(values=cols)
    #Analysis
    window["-ANALYSIS_GROUP1-"].update(values=cols)
    window["-ANALYSIS_GROUP2-"].update(values=[""] + cols)
    window["-ANALYSIS_AGG_COL-"].update(values=cols)
    window["-ANALYSIS_COL_LIST-"].update(values=cols)
    #Validation
    window["-VAL_NUM_COL-"].update(values=cols)
    window["-VAL_DATE_COL-"].update(values=cols)
    window["-VAL_TEXT_COL-"].update(values=cols)


def update_merge_right_dropdown(window):
    if second_df is None:
        cols = []
    else:
        cols = list(second_df.columns)

    window["-MERGE_RIGHT_KEY-"].update(values=cols)


def show_message(window, msg: str):
    """Statuszeile aktualisieren (ohne dass es knallt, falls -STATUS- fehlt)."""
    try:
        window["-STATUS-"].update(msg)
    except Exception:
        print(f"[STATUS] {msg}")


# ---------------------------------------------------------
# Layout
# ---------------------------------------------------------

def make_layout():
    # ---------- HEADER ----------
    header = [
        [
            sg.Column([
                [
                    sg.Image(filename=str(ASSETS_DIR / "logo.png"), pad=(0, 0)),
                    sg.Text(
                        "Excel Automator Pro",
                        font=("Segoe UI", 20, "bold"),
                        text_color=COLOR_TEXT,
                        pad=(20, 0),
                    ),
                ]
            ], pad=(20, 20))
        ],
        [sg.HorizontalSeparator(color="#D0D7E2")],
    ]

    # ---------- Import ----------
    page_import = sg.Column(
        [
            [
                sg.Frame(
                    "Daten Import",
                    [
                        [sg.Text("Eingabedatei (CSV/Excel):")],
                        [
                            sg.Input(key="-IMPORT_FILE-", size=(50, 1)),
                            sg.FileBrowse("Durchsuchen"),
                        ],
                        [
                            sg.Button(
                                "Datei laden",
                                key="-BTN_LOAD-",
                                button_color=("white", COLOR_PRIMARY),
                            )
                        ],
                        [sg.Multiline(size=(80, 15), key="-IMPORT_INFO-")],
                    ],
                    background_color=COLOR_CARD,
                    pad=(10, 10),
                )
            ]
        ],
        key="-PAGE_IMPORT-",
        visible=True,
    )

        # ---------- Cleaning + Validation ----------
    page_clean = sg.Column([
        [sg.Text("Bereinigung & Validierung der aktiven Daten", font=("Segoe UI", 10, "bold"))],

        # --- Block: klassische Bereinigung ---
        [sg.Frame(
            "Bereinigung",
            [
                [sg.Checkbox("Leere Zeilen entfernen", default=True, key="-CLEAN_EMPTY-")],
                [
                    sg.Text("Duplikate entfernen anhand Spalte:"),
                    sg.Combo([], key="-CLEAN_DUP_COL-", size=(30, 1))
                ],
                [sg.Button("Bereinigung ausführen", key="-BTN_CLEAN-", button_color=("white", COLOR_PRIMARY))]
            ],
            background_color=COLOR_CARD,
            pad=(10, 10),
        )],

        # --- Block: Validierung ---
        [sg.Frame(
            "Datenprüfung & Validierung",
            [
                [sg.Text("Numerische Prüfung:", font=("Segoe UI", 9, "bold"))],
                [
                    sg.Text("Spalte:", size=(8, 1)),
                    sg.Combo([], key="-VAL_NUM_COL-", size=(25, 1)),
                    sg.Text("Min:", size=(4, 1)),
                    sg.Input(key="-VAL_NUM_MIN-", size=(8, 1)),
                    sg.Text("Max:", size=(4, 1)),
                    sg.Input(key="-VAL_NUM_MAX-", size=(8, 1)),
                ],
                [sg.Text("Datumsprüfung (z.B. 2020-01-01 oder 01.01.2020):", font=("Segoe UI", 9, "bold"))],
                [
                    sg.Text("Spalte:", size=(8, 1)),
                    sg.Combo([], key="-VAL_DATE_COL-", size=(25, 1)),
                    sg.Text("Min:", size=(4, 1)),
                    sg.Input(key="-VAL_DATE_MIN-", size=(10, 1)),
                    sg.Text("Max:", size=(4, 1)),
                    sg.Input(key="-VAL_DATE_MAX-", size=(10, 1)),
                ],
                [sg.Text("Text-Normalisierung:", font=("Segoe UI", 9, "bold"))],
                [
                    sg.Text("Spalte:", size=(8, 1)),
                    sg.Combo([], key="-VAL_TEXT_COL-", size=(25, 1)),
                    sg.Text("Modus:", size=(6, 1)),
                    sg.Combo(
                        [
                            "Großschreibung (UPPER)",
                            "Kleinschreibung (lower)",
                            "Title Case",
                        ],
                        default_value="Großschreibung (UPPER)",
                        key="-VAL_TEXT_MODE-",
                        size=(24, 1),
                    ),
                ],
                [sg.Button("Daten prüfen", key="-BTN_VALIDATE-", button_color=("white", COLOR_PRIMARY))],
            ],
            background_color=COLOR_CARD,
            pad=(10, 10),
        )],

        # Ausgabe für Bereinigung + Validierung
        [sg.Multiline(size=(80, 12), key="-CLEAN_INFO-")],
    ], key="-PAGE_CLEAN-", visible=False)

    # ---------- Merge ----------
    page_merge = sg.Column(
        [
            [sg.Text("Zweite Datei zum Merge auswählen")],
            [
                sg.Input(key="-MERGE_FILE-"),
                sg.FileBrowse("Durchsuchen"),
            ],
            [
                sg.Button(
                    "Zweite Datei laden",
                    key="-BTN_LOAD_SECOND-",
                    button_color=("white", COLOR_PRIMARY),
                )
            ],
            [sg.HorizontalSeparator()],
            [sg.Text("Merge Einstellungen")],
            [
                sg.Text("Linker Schlüssel:"),
                sg.Combo([], size=(30, 1), key="-MERGE_LEFT_KEY-"),
            ],
            [
                sg.Text("Rechter Schlüssel:"),
                sg.Combo([], size=(30, 1), key="-MERGE_RIGHT_KEY-"),
            ],
            [
                sg.Text("Merge-Typ:"),
                sg.Combo(
                    ["inner", "left", "right", "outer"],
                    default_value="inner",
                    size=(10, 1),
                    key="-MERGE_HOW-",
                ),
            ],
            [
                sg.Button(
                    "Merge ausführen",
                    key="-BTN_MERGE-",
                    button_color=("white", COLOR_PRIMARY),
                )
            ],
            [sg.Multiline(size=(80, 12), key="-MERGE_INFO-")],
        ],
        key="-PAGE_MERGE-",
        visible=False,
    )

    # ---------- Analyse ----------
    analysis_buttons = []
    if ADVANCED_AVAILABLE:
        analysis_buttons = [
            sg.Button("Top-Listen", key="-BTN_TOPLISTS-", button_color=("white", COLOR_PRIMARY)),
            sg.Button("Zeitreihen", key="-BTN_TIMESERIES-", button_color=("white", COLOR_PRIMARY)),
            sg.Button("KPI-Report", key="-BTN_KPIS-", button_color=("white", COLOR_PRIMARY)),
            sg.Button("Quick Insights", key="-BTN_INSIGHTS-", button_color=("white", COLOR_PRIMARY)),
        ]

    page_analysis = sg.Column(
        [
            [sg.Text("Analyse", font=("Segoe UI", 10, "bold"))],
            analysis_buttons,
            [
                sg.Text("Gruppierspalte 1:"),
                sg.Combo([], size=(30, 1), key="-ANALYSIS_GROUP1-"),
            ],
            [
                sg.Text("Gruppierspalte 2:"),
                sg.Combo([], size=(30, 1), key="-ANALYSIS_GROUP2-"),
            ],
            [
                sg.Text("Aggregationsspalte:"),
                sg.Combo([], size=(30, 1), key="-ANALYSIS_AGG_COL-"),
            ],
            [
                sg.Text("Funktion:"),
                sg.Combo(
                    ["sum", "mean", "count", "min", "max"],
                    default_value="sum",
                    size=(10, 1),
                    key="-ANALYSIS_FUNC-",
                ),
            ],
            [
                sg.Button(
                    "Analyse ausführen",
                    key="-BTN_ANALYSIS-",
                    button_color=("white", COLOR_PRIMARY),
                )
            ],
            [sg.Multiline(size=(80, 15), key="-ANALYSIS_INFO-")],
            [sg.Text("Quick-Analyse per Klick:")],
            [
                sg.Listbox(
                    values=[],
                    size=(25, 12),
                    key="-ANALYSIS_COL_LIST-",
                    enable_events=True,
                )
            ],
        ],
        key="-PAGE_ANALYSIS-",
        visible=False,
    )

    # ---------- Export ----------
    page_export = sg.Column(
        [
            [sg.Text("Export nach Excel")],
            [
                sg.Text("Ziel:"),
                sg.Input("", key="-EXPORT_FILE-"),
                sg.FileSaveAs("Ziel wählen"),
            ],
            [sg.Checkbox("Aktive Daten exportieren", default=True, key="-EXPORT_MAIN-")],
            [sg.Checkbox("Analyse exportieren", default=True, key="-EXPORT_ANALYSIS-")],
            [
                sg.Button(
                    "Export starten",
                    key="-BTN_EXPORT-",
                    button_color=("white", COLOR_PRIMARY),
                )
            ],
            [sg.Multiline(size=(80, 12), key="-EXPORT_INFO-")],
        ],
        key="-PAGE_EXPORT-",
        visible=False,
    )

    # ---------- Jobs ----------
    page_jobs = sg.Column(
        [
            [sg.Text("Automatisierte Jobs")],
            [sg.Text("Job-Name:"), sg.Input(key="-JOB_NAME-")],
            [
                sg.Text("Input:"),
                sg.Input(key="-JOB_IN-"),
                sg.FileBrowse("Durchsuchen"),
            ],
            [
                sg.Text("Output:"),
                sg.Input(key="-JOB_OUT-"),
                sg.FileSaveAs("Ziel wählen"),
            ],
            [sg.Checkbox("Leere Zeilen entfernen", key="-JOB_CLEAN_EMPTY-", default=True)],
            [sg.Text("Duplikat-Spalte:"), sg.Input(key="-JOB_DUP_COL-")],
            [
                sg.Button(
                    "Job speichern",
                    key="-BTN_JOB_SAVE-",
                    button_color=("white", COLOR_PRIMARY),
                )
            ],
            [
                sg.Text("Job laden:"),
                sg.Input(key="-JOB_FILE-"),
                sg.FileBrowse("Job auswählen"),
                sg.Button(
                    "Job ausführen",
                    key="-BTN_JOB_RUN-",
                    button_color=("white", COLOR_PRIMARY),
                ),
            ],
            [sg.Multiline(size=(80, 12), key="-JOB_INFO-")],
        ],
        key="-PAGE_JOBS-",
        visible=False,
    )

    # ---------- PPT Export ----------
    page_ppt = sg.Column(
        [
            [sg.Text("PowerPoint Report")],
            [
                sg.Text("Zieldatei:"),
                sg.Input(str(BASE_DIR / "report.pptx"), key="-PPTX_FILE-"),
                sg.FileSaveAs("Ziel wählen"),
            ],
            [sg.Text("Titel:"), sg.Input("Automatisierter Auswertungsreport", key="-PPTX_TITLE-")],
            [sg.Text("Untertitel:"), sg.Input("Erstellt mit Excel Automator", key="-PPTX_SUBTITLE-")],
            [
                sg.Button(
                    "PPTX-Report erstellen",
                    key="-BTN_PPTX_EXPORT-",
                    button_color=("white", COLOR_PRIMARY),
                )
            ],
            [sg.Multiline(size=(80, 12), key="-PPTX_INFO-")],
        ],
        key="-PAGE_PPTX-",
        visible=False,
    )

    # ---------- Lizenz ----------
    machine_id = get_machine_id()

    page_license = sg.Column(
        [
            [sg.Text("Lizenzverwaltung")],
            [
                sg.Text("Maschinen-ID:"),
                sg.Input(machine_id, disabled=True, size=(40, 1), key="-LIC_MACHINE-"),
            ],
            [
                sg.Text("Lizenzschlüssel:"),
                sg.Input(key="-LIC_KEY-", size=(40, 1)),
                sg.Button(
                    "Lizenz prüfen & speichern",
                    key="-BTN_LIC_SAVE-",
                    button_color=("white", COLOR_PRIMARY),
                ),
            ],
            [sg.Multiline(size=(80, 5), key="-LIC_STATUS-", disabled=True)],
        ],
        key="-PAGE_LICENSE-",
        visible=False,
    )

    # ---------- Impressum ----------
    page_imprint = sg.Column(
        [
            [sg.Text("Impressum", font=("Segoe UI", 12, "bold"))],
            [sg.Multiline(IMPRINT_TEXT, size=(80, 12), disabled=True)],
        ],
        key="-PAGE_IMPRINT-",
        visible=False,
    )

    # ---------- Sidebar ----------
    sidebar = sg.Column(
        [
            [sg.Text("Navigation", font=("Segoe UI", 12, "bold"), pad=(10, 10))],
            [sg.Button("Import", key="-NAV_IMPORT-", size=(15, 1))],
            [sg.Button("Bereinigung", key="-NAV_CLEAN-", size=(15, 1))],
            [sg.Button("Merge", key="-NAV_MERGE-", size=(15, 1))],
            [sg.Button("Analyse", key="-NAV_ANALYSIS-", size=(15, 1))],
            [sg.Button("Export", key="-NAV_EXPORT-", size=(15, 1))],
            [sg.Button("Jobs", key="-NAV_JOBS-", size=(15, 1))],
            [sg.Button("PPTX", key="-NAV_PPTX-", size=(15, 1))],
            [sg.Button("Lizenz", key="-NAV_LICENSE-", size=(15, 1))],
            [sg.Button("Impressum", key="-NAV_IMPRINT-", size=(15, 1))],
        ]
    )

    # ---------- Content area ----------
        # ---------- Content area ----------
    content_area = sg.Column(
        [[
            page_import,
            page_clean,
            page_merge,
            page_analysis,
            page_export,
            page_jobs,
            page_ppt,
            page_license,
            page_imprint,
        ]],
        key="-CONTENT-",
        expand_x=True,
        expand_y=True,
        background_color=COLOR_BG,
    )

    # ---------- Full Layout ----------
    layout = [
        *header,
        [sidebar, content_area],
        [sg.HorizontalSeparator(color="#D0D7E2")],
        [sg.Text("Bereit", key="-STATUS-", font=("Segoe UI", 9), background_color=COLOR_BG)],
    ]

    return layout


# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------

def main():
    global current_df, current_df_name, second_df, merged_df, analysis_df
    global license_valid, license_message

    window = sg.Window("Excel Automator Pro", make_layout(), resizable=True, finalize=True)

    # Lizenz prüfen
    machine_id = get_machine_id()
    saved_key = load_saved_license(LICENSE_FILE)

    if saved_key:
        ok, msg = validate_license_key(machine_id, saved_key)
        license_valid = ok
        license_message = msg
    else:
        license_valid = False
        license_message = "Keine Lizenz gespeichert. Bitte Lizenz eingeben."

    try:
        window["-LIC_STATUS-"].update(license_message)
    except Exception:
        print("WARN: -LIC_STATUS- nicht gefunden – Layout prüfen.")

    # -------------------------
    # EVENT LOOP
    # -------------------------
    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED:
            break

        if event is None:
            continue

        print("EVENT:", event)  # Debug-Ausgabe

        # ---------------------------------
        # LIZENZ
        # ---------------------------------
        if event == "-BTN_LIC_SAVE-":
            key = values["-LIC_KEY-"].strip()
            ok, msg = validate_license_key(machine_id, key)
            license_valid = ok
            license_message = msg
            window["-LIC_STATUS-"].update(msg)

            if ok:
                save_license_key(LICENSE_FILE, key)
                show_message(window, "Lizenz gespeichert.")
            else:
                show_message(window, "Lizenz ungültig.")

        # ---------------------------------
        # IMPORT
        # ---------------------------------
        if event == "-BTN_LOAD-":
            print("DEBUG: BTN_LOAD ausgelöst")
            if not license_valid:
                show_message(window, "Lizenz ungültig – Import gesperrt.")
                continue

            path = values["-IMPORT_FILE-"]
            if not path:
                show_message(window, "Bitte Datei auswählen.")
                continue

            try:
                current_df = load_file(path)
                current_df_name = Path(path).name
                window["-IMPORT_INFO-"].update(profile_dataframe(current_df, current_df_name))
                update_column_dropdowns(window)
                show_message(window, f"Datei geladen: {current_df_name}")
            except Exception as e:
                window["-IMPORT_INFO-"].update(str(e))
                show_message(window, "Fehler beim Import.")

        # ---------------------------------
        # CLEANING
        # ---------------------------------
        if event == "-BTN_CLEAN-":
            print("DEBUG: BTN_CLEAN ausgelöst")
            if not license_valid:
                show_message(window, "Lizenz ungültig – Bereinigung gesperrt.")
                continue

            if current_df is None:
                show_message(window, "Keine Daten geladen.")
                continue

            remove_empty = values["-CLEAN_EMPTY-"]
            dup_col = values["-CLEAN_DUP_COL-"]

            try:
                before = len(current_df)
                current_df = clean_dataframe(
                    current_df,
                    remove_empty_rows=remove_empty,
                    duplicate_subset=dup_col or None,
                )
                after = len(current_df)
                window["-CLEAN_INFO-"].update(
                    f"Bereinigung abgeschlossen:\nVorher: {before}\nNachher: {after}"
                )
                update_column_dropdowns(window)
                show_message(window, "Bereinigung erfolgreich.")
            except Exception as e:
                window["-CLEAN_INFO-"].update(str(e))
                show_message(window, "Fehler bei Bereinigung.")
                # ---------------------------------
        # VALIDIERUNG (B, C, D)
        # ---------------------------------
        if event == "-BTN_VALIDATE-":
            if not license_valid:
                show_message(window, "Lizenz ungültig – Validierung gesperrt.")
                continue

            if current_df is None:
                show_message(window, "Keine Daten geladen – bitte zuerst Datei importieren.")
                continue

            reports = []

            # --- numerische Prüfung ---
            num_col = values["-VAL_NUM_COL-"]
            num_min = values["-VAL_NUM_MIN-"].strip()
            num_max = values["-VAL_NUM_MAX-"].strip()

            def _parse_float_safe(val: str):
                if not val:
                    return None
                try:
                    return float(val.replace(",", "."))
                except ValueError:
                    return None

            if num_col:
                min_val = _parse_float_safe(num_min)
                max_val = _parse_float_safe(num_max)
                res_num = validate_numeric_range(current_df, num_col, min_val, max_val)
                reports.append(res_num.message)

            # --- Datumsprüfung ---
            date_col = values["-VAL_DATE_COL-"]
            date_min = values["-VAL_DATE_MIN-"].strip()
            date_max = values["-VAL_DATE_MAX-"].strip()

            if date_col:
                res_date = validate_date_range(current_df, date_col, date_min, date_max)
                reports.append(res_date.message)

            # --- Text-Normalisierung ---
            text_col = values["-VAL_TEXT_COL-"]
            mode_raw = values["-VAL_TEXT_MODE-"]

            mode_map = {
                "Großschreibung (UPPER)": "upper_strip",
                "Kleinschreibung (lower)": "lower_strip",
                "Title Case": "title_strip",
            }
            mode = mode_map.get(mode_raw, "upper_strip")

            if text_col:
                current_df, res_text = normalize_text_column(current_df, text_col, mode=mode)
                reports.append(res_text.message)
                # Spaltenliste aktualisieren, da neue *_norm-Spalte hinzugekommen sein kann
                update_column_dropdowns(window)

            if reports:
                window["-CLEAN_INFO-"].update("\n\n".join(reports))
                show_message(window, "Validierung abgeschlossen.")
            else:
                window["-CLEAN_INFO-"].update("Keine Prüfregeln ausgewählt.")
                show_message(window, "Keine Prüfregeln ausgewählt.")

        # ---------------------------------
        # MERGE: Zweite Datei laden
        # ---------------------------------
        if event == "-BTN_LOAD_SECOND-":
            print("DEBUG: BTN_LOAD_SECOND ausgelöst")
            path = values["-MERGE_FILE-"]
            if not path:
                show_message(window, "Bitte Datei wählen.")
                continue
            try:
                second_df = load_file(path)
                update_merge_right_dropdown(window)
                window["-MERGE_INFO-"].update(
                    "Zweite Datei geladen.\n" + profile_dataframe(second_df, Path(path).name)
                )
                show_message(window, "Zweite Datei geladen.")
            except Exception as e:
                window["-MERGE_INFO-"].update(str(e))
                show_message(window, "Fehler beim Laden.")

        # ---------------------------------
        # MERGE ausführen
        # ---------------------------------
        if event == "-BTN_MERGE-":
            print("DEBUG: BTN_MERGE ausgelöst")
            if current_df is None or second_df is None:
                show_message(window, "Beide Dateien nötig.")
                continue

            left = values["-MERGE_LEFT_KEY-"]
            right = values["-MERGE_RIGHT_KEY-"]
            how = values["-MERGE_HOW-"]

            try:
                merged = merge_dataframes(current_df, second_df, left, right, how)
                current_df = merged
                update_column_dropdowns(window)
                window["-MERGE_INFO-"].update(
                    "Merge erfolgreich.\n" + profile_dataframe(current_df, "Merge")
                )
                show_message(window, "Merge erfolgreich.")
            except Exception as e:
                window["-MERGE_INFO-"].update(str(e))
                show_message(window, "Fehler bei Merge.")

        # ---------------------------------
        # Quick Analyse (Spaltenliste)
        # ---------------------------------
        if event == "-ANALYSIS_COL_LIST-":
            print("DEBUG: ANALYSIS_COL_LIST ausgelöst")
            if current_df is None:
                continue
            col = values["-ANALYSIS_COL_LIST-"][0]
            try:
                df = quick_column_insight(current_df, col)
                window["-ANALYSIS_INFO-"].update(df.to_string())
                analysis_df = df
                show_message(window, f"Schnell-Analyse: {col}")
            except Exception as e:
                window["-ANALYSIS_INFO-"].update(str(e))
                show_message(window, "Fehler bei Quick Analyse.")

        # ---------------------------------
        # Standard Analyse
        # ---------------------------------
        if event == "-BTN_ANALYSIS-":
            print("DEBUG: BTN_ANALYSIS ausgelöst")
            if current_df is None:
                continue

            g1 = values["-ANALYSIS_GROUP1-"]
            g2 = values["-ANALYSIS_GROUP2-"]
            agg = values["-ANALYSIS_AGG_COL-"]
            func = values["-ANALYSIS_FUNC-"]

            group_cols = [c for c in (g1, g2) if c]

            try:
                df = basic_group_analysis(current_df, group_cols, agg, func)
                analysis_df = df
                window["-ANALYSIS_INFO-"].update(df.to_string())
                show_message(window, "Analyse erfolgreich.")
            except Exception as e:
                window["-ANALYSIS_INFO-"].update(str(e))
                show_message(window, "Analyse fehlgeschlagen.")

        # ---------------------------------
        # Advanced Analysis (falls vorhanden)
        # ---------------------------------
        if ADVANCED_AVAILABLE:
            if event == "-BTN_TOPLISTS-":
                print("DEBUG: BTN_TOPLISTS ausgelöst")
                df = generate_top_lists(current_df)
                txt = ""
                for col, serie in df.items():
                    txt += f"Top Werte {col}:\n{serie.to_string()}\n\n"
                window["-ANALYSIS_INFO-"].update(txt)
                show_message(window, "Top-Listen erstellt.")

            if event == "-BTN_TIMESERIES-":
                print("DEBUG: BTN_TIMESERIES ausgelöst")
                ts = time_series_analysis(current_df)
                out = ""
                for col, groups in ts.items():
                    out += f"Zeitreihe {col}:\n"
                    for name, ser in groups.items():
                        out += f"{name}:\n{ser.to_string()}\n\n"
                window["-ANALYSIS_INFO-"].update(out)

            if event == "-BTN_KPIS-":
                print("DEBUG: BTN_KPIS ausgelöst")
                k = generate_kpis(current_df)
                out = "\n".join(f"{key}: {value}" for key, value in k.items())
                window["-ANALYSIS_INFO-"].update(out)

            if event == "-BTN_INSIGHTS-":
                print("DEBUG: BTN_INSIGHTS ausgelöst")
                window["-ANALYSIS_INFO-"].update(quick_insights(current_df))

        # ---------------------------------
        # EXPORT
        # ---------------------------------
        if event == "-BTN_EXPORT-":
            print("DEBUG: BTN_EXPORT ausgelöst")
            path = values["-EXPORT_FILE-"]
            if not path:
                show_message(window, "Bitte Datei nennen.")
                continue

            export_main = values["-EXPORT_MAIN-"]
            export_analysis = values["-EXPORT_ANALYSIS-"]

            df_main = current_df if export_main else None
            df_analysis = analysis_df if export_analysis else None

            try:
                export_to_excel(path, df_main, df_analysis)
                window["-EXPORT_INFO-"].update(f"Export erfolgreich:\n{path}")
                show_message(window, "Export erfolgreich.")
            except Exception as e:
                window["-EXPORT_INFO-"].update(str(e))
                show_message(window, "Fehler beim Export.")

        # ---------------------------------
        # JOB speichern
        # ---------------------------------
        if event == "-BTN_JOB_SAVE-":
            print("DEBUG: BTN_JOB_SAVE ausgelöst")
            name = values["-JOB_NAME-"].strip()
            input_file = values["-JOB_IN-"]
            output_file = values["-JOB_OUT-"]
            clean_empty = values["-JOB_CLEAN_EMPTY-"]
            dup_col = values["-JOB_DUP_COL-"]

            if not name or not input_file or not output_file:
                show_message(window, "Bitte alles ausfüllen.")
                continue

            config = {
                "name": name,
                "input": input_file,
                "output": output_file,
                "clean_empty": clean_empty,
                "dup_col": dup_col or None,
            }

            job_path = JOBS_DIR / f"{name}.json"

            save_job(config, str(job_path))
            window["-JOB_INFO-"].update(f"Job gespeichert unter:\n{job_path}")
            show_message(window, "Job gespeichert.")

        # ---------------------------------
        # JOB ausführen
        # ---------------------------------
        if event == "-BTN_JOB_RUN-":
            print("DEBUG: BTN_JOB_RUN ausgelöst")
            jobfile = values["-JOB_FILE-"]

            if not jobfile:
                show_message(window, "Bitte Job wählen.")
                continue

            try:
                job = load_job(jobfile)
                df = load_file(job["input"])
                df = clean_dataframe(
                    df,
                    remove_empty_rows=job["clean_empty"],
                    duplicate_subset=job["dup_col"],
                )
                export_to_excel(job["output"], df, None)

                window["-JOB_INFO-"].update(f"Job ausgeführt.\nOutput: {job['output']}")
                show_message(window, "Job erfolgreich.")
            except Exception as e:
                window["-JOB_INFO-"].update(str(e))
                show_message(window, "Fehler bei Job.")

        # ---------------------------------
        # PPTX EXPORT
        # ---------------------------------
        if event == "-BTN_PPTX_EXPORT-":
            print("DEBUG: BTN_PPTX_EXPORT ausgelöst")
            if analysis_df is None:
                show_message(window, "Keine Analyse vorhanden.")
                continue

            path = values["-PPTX_FILE-"]
            title = values["-PPTX_TITLE-"]
            subtitle = values["-PPTX_SUBTITLE-"]

            try:
                out = export_analysis_to_pptx(path, analysis_df, title, subtitle)
                window["-PPTX_INFO-"].update(f"Report erstellt:\n{out}")
                show_message(window, "PPTX Export erfolgreich.")
            except Exception as e:
                window["-PPTX_INFO-"].update(str(e))
                show_message(window, "Fehler bei PPTX.")

        # ---------------------------------
        # Navigation
        # ---------------------------------
        if event.startswith("-NAV_"):
            print("DEBUG: Navigation ausgelöst:", event)
            for page in [
                "-PAGE_IMPORT-",
                "-PAGE_CLEAN-",
                "-PAGE_MERGE-",
                "-PAGE_ANALYSIS-",
                "-PAGE_EXPORT-",
                "-PAGE_JOBS-",
                "-PAGE_PPTX-",
                "-PAGE_LICENSE-",
                "-PAGE_IMPRINT-",
            ]:
                window[page].update(visible=False)

            target = event.replace("-NAV_", "-PAGE_")
            window[target].update(visible=True)
            show_message(window, f"Seite gewechselt: {target}")

    window.close()


if __name__ == "__main__":
    print("Starte Excel Automator Pro…")
    main()
    print("Programm beendet.")
