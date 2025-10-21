"""
scaffold_loader.py
Univerzalni loader za Jam.py scaffold sisteme.

Automatski prepoznaje drajver (sqlite, mysql, postgres, firebird)
i poziva odgovarajući scaffold_{driver}.py modul.
"""

import importlib
import sys
import scaffold_common as common


# ============================================================
# ⚙️ GLAVNA FUNKCIJA
# ============================================================
def run_scaffold(db_info: dict):
    """
    Pokreće odgovarajući scaffold modul na osnovu drajvera.
    
    db_info primer:
    {
        "driver": "mysql",
        "db": "primer_db",
        "host": "localhost",
        "user": "root",
        "password": "pass",
        "admin_path": "admin.sqlite",
        "group": 1,
        "owner": 1
    }
    """

    driver = db_info.get("driver", "sqlite").lower().strip()
    module_name = f"scaffold_{driver}"

    common.debug(f"🔍 Detektovan drajver: {driver}")

    try:
        scaffold_module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        raise ImportError(f"❌ Modul {module_name}.py nije pronađen!")

    if not hasattr(scaffold_module, "connect_to_database") or not hasattr(scaffold_module, "my_database_procedure"):
        raise AttributeError(f"❌ Modul {module_name} ne implementira potrebne funkcije!")

    common.debug(f"⚙️ Pokrećem scaffold iz {module_name}.py")

    # 1️⃣ Konekcija
    conn = scaffold_module.connect_to_database(db_info)
    if not conn:
        raise RuntimeError(f"❌ Nije moguće uspostaviti konekciju ({driver})")

    # 2️⃣ Scaffold proces
    scaffold_module.my_database_procedure(conn, db_info)

    # 3️⃣ Zatvaranje konekcije
    try:
        conn.close()
    except Exception:
        pass

    common.debug(f"✅ Scaffold kompletiran za drajver: {driver}")


# ============================================================
# 🚀 CLI ENTRY TAČKA
# ============================================================
if __name__ == "__main__":
    # primer ručnog pokretanja
    db_info = {
        "driver": "sqlite",  # ili mysql / postgres / firebird
        "db": "primer.db",
        "admin_path": "admin.sqlite",
        "group": 1,
        "owner": 1,
        "user": "root",
        "password": "test",
        "host": "localhost",
        "port": 5432
    }
    run_scaffold(db_info)
