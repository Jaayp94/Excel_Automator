from ea_core.license import get_machine_id, generate_license_key_for_machine

if __name__ == "__main__":
    machine_id = get_machine_id()
    print(f"Maschinen-ID: {machine_id}")

    key = generate_license_key_for_machine(machine_id, valid_days=365)
    print("Lizenzschlüssel (12 Monate gültig):")
    print(key)
