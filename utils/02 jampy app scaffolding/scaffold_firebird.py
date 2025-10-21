"""
scaffold_firebird.py
Scaffold implementacija za Firebird bazu (Jam.py kompatibilna).
Koristi zajednički modul scaffold_common.
"""

import fdb  # Firebird SQL driver
from pathlib import Path
import scaffold_common as common


# KONEKCIJA
def connect_to_database(db_info: dict):
    """Uspostavlja konekciju sa Firebird bazom."""
    try:
        conn = fdb.connect(
            dsn=f"{db_info.get('host', 'localhost')}/{db_info.get('port', 3050)}:{db_info.get('db')}",
            user=db_info.get("user", "sysdba"),
            password=db_info.get("password", "masterkey")
        )
        common.debug(f"Povezivanje na Firebird bazu: {db_info.get('db')}")
        return conn
    except Exception as e:
        raise ConnectionError(f"Greška pri konekciji na Firebird: {e}")



# STRUKTURA BAZE
def get_table_names(conn):
    """Vraća listu tabela iz Firebird baze."""
    cur = conn.cursor()
    cur.execute("""
        SELECT RDB$RELATION_NAME
        FROM RDB$RELATIONS
        WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL;
    """)
    tables = [r[0].strip() for r in cur.fetchall()]
    cur.close()
    common.debug(f"Pronađeno tabela: {tables}")
    return tables


def get_table_info(conn, table_name: str):
    """Vraća detalje o kolonama u tabeli."""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            rf.RDB$FIELD_NAME,
            f.RDB$FIELD_TYPE,
            f.RDB$FIELD_SUB_TYPE,
            COALESCE(f.RDB$FIELD_LENGTH, 0),
            COALESCE(f.RDB$FIELD_PRECISION, 0),
            COALESCE(f.RDB$FIELD_SCALE, 0),
            COALESCE(rf.RDB$NULL_FLAG, 0)
        FROM RDB$RELATION_FIELDS rf
        JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
        WHERE rf.RDB$RELATION_NAME = ?
        ORDER BY rf.RDB$FIELD_POSITION;
    """, (table_name,))
    columns = []
    for row in cur.fetchall():
        name = row[0].strip()
        col_type = f"TYPE_{row[1]}"
        not_null = bool(row[6])
        pk = is_primary_key(conn, table_name, name)
        columns.append({
            "col_name": name,
            "col_type": col_type,
            "col_constraints": "",
            "pk": pk,
            "not_null": not_null
        })
    cur.close()
    return columns


def is_primary_key(conn, table_name: str, col_name: str) -> bool:
    """Proverava da li je kolona primarni ključ u Firebird tabeli."""
    cur = conn.cursor()
    cur.execute("""
        SELECT sg.RDB$FIELD_NAME
        FROM RDB$INDEX_SEGMENTS sg
        JOIN RDB$INDICES i ON i.RDB$INDEX_NAME = sg.RDB$INDEX_NAME
        WHERE i.RDB$RELATION_NAME = ? AND i.RDB$UNIQUE_FLAG = 1;
    """, (table_name,))
    pk_cols = [r[0].strip() for r in cur.fetchall()]
    cur.close()
    return col_name in pk_cols



# UPIS U admin.sqlite
def write_to_admin(conn_src, admin_path: Path, db_info: dict):
    """Upisuje tabele i kolone iz Firebird baze u Jam.py admin.sqlite."""
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


# GLAVNA ENTRY TAČKA
def my_database_procedure(conn, db_info: dict):
    """Glavna procedura – povezuje sve korake."""
    admin_path = Path(db_info.get("admin_path", "admin.sqlite"))
    common.debug(f"Pokrećem scaffold za Firebird → {admin_path}")
    write_to_admin(conn, admin_path, db_info)
    common.debug("Scaffold Firebird završio uspešno.")
