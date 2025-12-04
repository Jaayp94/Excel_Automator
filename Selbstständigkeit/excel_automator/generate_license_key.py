# license_key_generator.py
"""
Kleines Tool für DICH als Entwickler,
um aus einer Maschinen-ID einen Lizenzschlüssel zu erzeugen.

Benutzung:
    1. Kunde startet Excel Automator → Tab "Lizenz"
    2. Kunde schickt dir die Maschinen-ID (z.B. ABCD1234EFGH5678)
    3. Du startest dieses Script:
           python license_key_generator.py
    4. Maschinen-ID einfügen, optional Ablaufdatum eingeben
    5. Lizenzschlüssel kopieren und dem Kunden schicken
"""

from ea_core.license import generate_license_key


def main():
    print("=== Excel Automator Pro – Lizenzgenerator ===\n")

    machine_id = input("Maschinen-ID des Kunden eingeben: ").strip()
    if not machine_id:
        print("Keine Maschinen-ID eingegeben – Abbruch.")
        return

    expires = input(
        "Ablaufdatum (YYYY-MM-DD) oder leer für unbefristete Lizenz: "
    ).strip()

    if not expires:
        expires = None

    key = generate_license_key(machine_id, expires)

    print("\n--- Lizenzschlüssel ---")
    print(key)
    print("-----------------------")
    print("\nDiesen Schlüssel kann der Kunde im Tab 'Lizenz' eintragen.")


if __name__ == "__main__":
    main()
