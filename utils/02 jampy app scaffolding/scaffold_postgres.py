"""
scaffold_postgres.py
Scaffold implementacija za PostgreSQL bazu (Jam.py kompatibilna).
Koristi zajednički modul scaffold_common.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from pathlib import Path
import scaffold_common as common


# ============================================================
# 🔌 1. KONEKCIJA
# ============================================================
def connect_to_database(db_info: dict):
    """Uspostavlja konekciju sa PostgreSQL bazom."""
    try:
        conn = psycopg2.connect(
            dbname=db_info.get("db", ""),
            user=db_info.get("user", ""),
            password=db_info.get("password", ""),
            host=db_info.get("host", "localhost"),
            port=db_info.get("port", 5432)
        )
        common.debug(f"Povezivanje na PostgreSQL bazu: {db_info.get('db')}")
        return conn
    except Exception as e:
        raise ConnectionError(f"Greška pri konekciji na PostgreSQL: {e}")


# ============================================================
# 🧱 2. STRUKTURA BAZE
# ============================================================
def get_table_names(conn):
    """Vraća listu tabela iz PostgreSQL baze."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type='BASE TABLE';
    """)
    tables = [r[0] for r in cursor.fetchall()]
    cursor.close()
    common.debug(f"Pronađeno tabela: {tables}")
    return tables


def get_table_info(conn, table_name: str):
    """Vraća detalje o kolonama u tabeli."""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute(sql.SQL("""
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            ordinal_position
        FROM information_schema.columns
        WHERE table_name = %s;
    """), [table_name])
    columns = []
    for row in cursor.fetchall():
        columns.append({
            "col_name": row["column_name"],
            "col_type": row["data_type"],
            "col_constraints": "",
            "pk": is_primary_key(conn, table_name, row["column_name"]),
            "not_null": row["is_nullable"].upper() == "NO"
        })
    cursor.close()
    return columns


def is_primary_key(conn, table_name: str, col_name: str) -> bool:
    """Pomoćna funkcija: proverava da li je kolona primarni ključ."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY';
    """, [table_name])
    pk_cols = [r[0] for r in cursor.fetchall()]
    cursor.close()
    return col_name in pk_cols


# ============================================================
# 🧮 3. UPIS U admin.sqlite
# ============================================================
def write_to_admin(conn_src, admin_path: Path, db_info: dict):
    """Upisuje tabele i kolone iz PostgreSQL baze u Jam.py admin.sqlite."""
    import sqlite3
    if not admin_path.exists():
        raise FileNotFoundError(f"admin.sqlite nije pronađen na {admin_path}")

    conn_admin = sqlite3.connect(admin_path)
    cur_admin = conn_admin.cursor()

    cur_admin.execute("DELETE FROM SYS_ITEMS;")
    cur_admin.execute("DELETE FROM SYS_FIELDS;")

    tables = get_table_names(conn_src)
    item_id = common.ITEM_START_ID
    field_id = common.FIELD_START_ID

    for tname in tables:
        columns = get_table_info(conn_src, tname)

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
    common.debug(f"Pokrećem scaffold za PostgreSQL → {admin_path}")
    write_to_admin(conn, admin_path, db_info)
    common.debug("Scaffold PostgreSQL završio uspešno.")