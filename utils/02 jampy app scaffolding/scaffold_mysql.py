"""
scaffold_mysql.py
Scaffold implementacija za MySQL bazu (Jam.py kompatibilna).
Koristi zajednički modul scaffold_common za pomoćne funkcije i konstante.
"""

import mysql.connector
from mysql.connector import Error
import json
from pathlib import Path
import scaffold_common as common


# ============================================================
# 🔌 1. KONEKCIJA
# ============================================================
def connect_to_database(db_info: dict):
    """Uspostavlja konekciju sa MySQL bazom."""
    try:
        conn = mysql.connector.connect(
            host=db_info.get("host", "localhost"),
            user=db_info.get("user", ""),
            password=db_info.get("password", ""),
            database=db_info.get("db", ""),
            port=db_info.get("port", 3306)
        )
        if conn.is_connected():
            common.debug(f"Povezivanje na MySQL bazu: {db_info.get('db')}")
            return conn
    except Error as e:
        raise ConnectionError(f"Greška pri konekciji na MySQL: {e}")
    return None


# ============================================================
# 🧱 2. STRUKTURA BAZE
# ============================================================
def get_table_names(conn):
    """Vraća listu tabela iz MySQL baze."""
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tables = [r[0] for r in cursor.fetchall()]
    cursor.close()
    common.debug(f"Pronađeno tabela: {tables}")
    return tables


def get_table_info(conn, table_name: str):
    """Vraća detalje o kolonama u tabeli."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`;")
    columns = []
    for row in cursor.fetchall():
        columns.append({
            "col_name": row["Field"],
            "col_type": row["Type"],
            "col_constraints": row.get("Key", ""),
            "pk": row["Key"] == "PRI",
            "not_null": row["Null"].upper() == "NO"
        })
    cursor.close()
    return columns


# ============================================================
# 🧮 3. UPIS U admin.sqlite
# ============================================================
def write_to_admin(conn_src, admin_path: Path, db_info: dict):
    """Upisuje tabele i kolone iz MySQL baze u Jam.py admin.sqlite."""
    if not admin_path.exists():
        raise FileNotFoundError(f"admin.sqlite nije pronađen na {admin_path}")

    import sqlite3
    conn_admin = sqlite3.connect(admin_path)
    cur_admin = conn_admin.cursor()

    # brišemo postojeće meta-podatke
    cur_admin.execute("DELETE FROM SYS_ITEMS;")
    cur_admin.execute("DELETE FROM SYS_FIELDS;")

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
        cur_admin.execute("""
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
            cur_admin.execute("""
                INSERT INTO SYS_FIELDS
                (id, f_table, f_name, f_caption, f_data_type, f_not_null, f_primary_key, f_info)
                VALUES (:id, :f_table, :f_name, :f_caption, :f_data_type, :f_not_null, :f_primary_key, :f_info)
            """, field_rec)
            field_id += 1

        item_id += 1

    conn_admin.commit()
    conn_admin.close()
    common.debug(f"Zapisano {len(tables)} tabela u admin.sqlite ({admin_path})")


# ============================================================
# 🏗️ 4. GLAVNA ENTRY TAČKA
# ============================================================
def my_database_procedure(conn, db_info: dict):
    """Glavna procedura – povezuje sve korake."""
    admin_path = Path(db_info.get("admin_path", "admin.sqlite"))
    common.debug(f"Pokrećem scaffold za MySQL → {admin_path}")
    write_to_admin(conn, admin_path, db_info)
    common.debug("Scaffold MySQL završio uspešno.")


# ============================================================
# ✅ 5. GLAVNI SCENARIO (CLI FRIENDLY)
# ============================================================
if __name__ == "__main__":
    # primer testnog pokretanja
    info = {
        "db": "primer_db",
        "host": "localhost",
        "user": "root",
        "password": "password",
        "admin_path": "admin.sqlite",
        "group": 1,
        "owner": 1
    }
    conn = connect_to_database(info)
    if conn:
        my_database_procedure(conn, info)
        conn.close()
        print("✅ Scaffold MySQL kompletiran.")