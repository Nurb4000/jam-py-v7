"""
Scaffold implementacija za SQLite bazu (Jam.py kompatibilna).
Korišćenje zajedničkog modula scaffold_common za pomoćne funkcije i konstante.
"""

import sqlite3
import json
from pathlib import Path
import scaffold_common as common

# KONEKCIJA
def connect_to_database(db_info: dict) -> sqlite3.Connection:
    """Uspostavlja konekciju sa SQLite bazom."""
    db_path = db_info.get("db")
    if not db_path:
        raise ValueError("Nedostaje putanja do SQLite baze (db_info['db']).")

    common.debug(f"Povezivanje na SQLite bazu: {db_path}")
    return sqlite3.connect(db_path)

# STRUKTURA BAZE
def get_table_names(conn: sqlite3.Connection):
    """Vraća listu tabela iz SQLite baze."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cur.fetchall()]
    common.debug(f"Pronađeno tabela: {tables}")
    return tables

def get_table_info(conn: sqlite3.Connection, table_name: str):
    """Vraća detalje o kolonama u tabeli."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = []
    for cid, name, col_type, notnull, dflt_value, pk in cur.fetchall():
        columns.append({
            "col_name": name,
            "col_type": col_type or "TEXT",
            "col_constraints": "",
            "pk": bool(pk),
            "not_null": bool(notnull)
        })
    return columns

# UPIS U admin.sqlite
def write_to_admin(conn_src: sqlite3.Connection, admin_path: Path, db_info: dict):
    """Upisuje tabele i kolone iz izvorne baze u Jam.py admin.sqlite."""
    if not admin_path.exists():
        raise FileNotFoundError(f"admin.sqlite nije pronađen na {admin_path}")

    conn_admin = sqlite3.connect(admin_path)
    cur_admin = conn_admin.cursor()

    # brišemo postojeće meta-podatke, ali samo one koje smo prethodno dodali
    cur_admin.execute("DELETE FROM `SYS_ITEMS` WHERE `id`>=6;")
    cur_admin.execute("DELETE FROM `SYS_FIELDS` WHERE `id`>=12;")

    tables = get_table_names(conn_src)
    item_id = common.ITEM_START_ID
    field_id = common.FIELD_START_ID

    for tname in tables:
        columns = get_table_info(conn_src, tname)

        # Kreiraj zapis za SYS_ITEMS
        item_rec = common.build_item_record(
            name=tname,
            item_id=item_id,
            group=db_info.get("group", common.DEFAULT_GROUP),
            owner=db_info.get("owner", common.DEFAULT_OWNER)
        )
        cur_admin.execute(
        """
            INSERT INTO SYS_ITEMS (id, f_name, f_caption, f_group, f_owner, f_info)
            VALUES (:id, :f_name, :f_caption, :f_group, :f_owner, :f_info)
        """, item_rec)

        # Kreiraj zapise za SYS_FIELDS
        for col in columns:
            field_rec = common.build_field_record(
                table_id=item_id,
                name=col["col_name"],
                col_type=col["col_type"],
                pk=col["pk"],
                not_null=col["not_null"],
                field_id=field_id
            )
            cur_admin.execute(
            """
                INSERT INTO SYS_FIELDS
                (id, f_table, f_name, f_caption, f_data_type, f_not_null, f_primary_key, f_info)
                VALUES (:id, :f_table, :f_name, :f_caption, :f_data_type, :f_not_null, :f_primary_key, :f_info)
            """, field_rec)
            field_id += 1

        item_id += 1

    conn_admin.commit()
    conn_admin.close()
    common.debug(f"Zapisano {len(tables)} tabela u admin.sqlite ({admin_path})")

# GLAVNA ENTRY TAČKA
def my_database_procedure(conn: sqlite3.Connection, db_info: dict):
    """Glavna procedura - povezuje sve korake."""
    admin_path = Path(db_info.get("admin_path", "admin.sqlite"))
    common.debug(f"Pokrećem scaffold za SQLite → {admin_path}")
    write_to_admin(conn, admin_path, db_info)
    common.debug("Scaffold SQLite završio uspešno.")

# GLAVNI SCENARIO (CLI FRIENDLY)
if __name__ == "__main__":
    # primer testnog pokretanja
    info = {
        "db": "primer.db",
        "admin_path": "admin.sqlite",
        "group": 1,
        "owner": 1
    }
    conn = connect_to_database(info)
    my_database_procedure(conn, info)
    conn.close()
    print("Scaffold SQLite kompletiran.")
