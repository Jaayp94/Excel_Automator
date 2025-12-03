# Python-Image als Basis
FROM python:3.11-slim

# Arbeitsverzeichnis im Container setzen
WORKDIR /app

# Kopiere requirements.txt und installiere alle Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere alle restlichen Dateien (app.py, templates/, static/, etc.)
COPY . .

# CSV-Verzeichnis für Logs anlegen (falls nicht vorhanden)
RUN mkdir -p /app/csv_logs

# Port 8080 für den Zugriff über Browser
EXPOSE 8080

# App startet beim Start des Containers
CMD ["python", "app.py"]
