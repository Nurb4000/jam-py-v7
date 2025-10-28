#!/usr/bin/env python

import sqlite3
import re
import json
import sqlparse
import os
import argparse
from collections import defaultdict
import re
from textblob import Word

# Global placeholder
args = None

# === CONFIGURATION ===
ADMIN_FILE = 'admin.sqlite'

RESERVED_FIELD_NAMES = {"active", "class", "def", "from", "global", "import", "lambda", "placeholder", "hidden", "progress", "task", "label", "badge", "order", "privileges", "name", "login", "password", "status", "permissions"}


# SYS_ITEMS config
ITEM_START_ID = 6
PARENT_ID = 2
TASK_ID = 1
TYPE_ID = 10
VISIBLE = 1
DELETED = 0
TABLE_ID = 0
F_VIRTUAL_TABLE = 0
F_SOFT_DELETE = 0

# SYS_FIELDS config
FIELD_START_ID = 12
OWNER_ID = 3
#F_ALIGNMENT = 1
F_TEXTAREA = 0
F_DO_NOT_SANITIZE = 0
F_CALC_LOOKUP_FIELD = 0
F_REQUIRED = 0

JAM_TYPES = TEXT, INTEGER, FLOAT, CURRENCY, DATE, DATETIME, BOOLEAN, LONGTEXT, KEYS, FILE, IMAGE = range(1, 12)

FIELD_TYPES = {
    INTEGER: 'INTEGER',
    TEXT: 'TEXT',
    FLOAT: 'REAL',
    CURRENCY: 'REAL',
    DATE: 'TEXT',
    DATETIME: 'TEXT',
    BOOLEAN: 'INTEGER',
    LONGTEXT: 'TEXT',
    KEYS: 'TEXT',
    FILE: 'TEXT',
    IMAGE: 'TEXT'
}

def normalize_plural(word):
    word = word.lower()
    if word.endswith('ies'):
        return word[:-3] + 'y'
#    elif word.endswith('es'):
#        return word[:-2]
    elif word.endswith('s'):
        return word[:-1]
    return word
def normalize_plural(word):
    return Word(word.lower()).singularize()

def get_group_key(suffix, known_roots):
    # === NEW: Handle ALLCAPS directly ===
    if suffix.isupper():
        root = normalize_plural(suffix)
        return root.capitalize()

    # Normal camelCase or snake_case
    parts = re.findall(r'[A-Z][a-z]*|[a-z]+', suffix)
    if parts:
        root = normalize_plural(parts[0])
        for known in known_roots:
            if normalize_plural(known.lower()) == root:
                return known.title()
        return root.title()

    # Fallback
    return suffix.title()


def group_by_suffix(tables, prefix=''):
    grouped = defaultdict(list)
    known_roots = set()

    for table in sorted(tables):
        prefix=args.prefix
        if table.lower().startswith(prefix.lower()):
            suffix = table[len(prefix):]
            group_key = get_group_key(suffix, known_roots)
            grouped[group_key].append(table)
            known_roots.add(group_key)
        else:
            grouped['Misc'].append(table)

    return dict(grouped)


def sanitize_field_name(name):
    return name + "_f" if name in RESERVED_FIELD_NAMES else name


def get_table_info(db_file, table_name):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}")')  # safer with quotes
    result = cursor.fetchall()
    fields = []
    for r in result:
        fields.append({
            'col_name': r[1],
            'col_type': r[2],
            'col_constraints': r[4],
            'pk': r[5] == 1
        })

    return {
        'fields': fields
    }
def get_table_info(db_file, table_name):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Get table column metadata
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    result = cursor.fetchall()

    fields = []
    has_id_column = False

    for r in result:
        col_name = r[1]
        col_type = r[2]
        col_constraints = r[4]
        is_pk = r[5] == 1

        # 👇 Check if column is 'ID' (case-insensitive)
        if col_name.upper() == 'ID':
            has_id_column = True
            is_pk = True  # Mark it as primary key even if not declared

        fields.append({
            'col_name': col_name,
            'col_type': col_type,
            'col_constraints': col_constraints,
            'pk': is_pk
        })

    return {
        'fields': fields,
        'has_id': has_id_column
    }
def get_foreign_keys(db_file, table_name):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
    fks = cursor.fetchall()
    conn.close()
    # Return a list of dicts for clarity
    return [
        {"from": fk[3], "to_table": fk[2], "to_column": fk[4]}
        for fk in fks
    ]



def get_table_names(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sqlite_master WHERE type='table'")
    result = cursor.fetchall()
    #print(f"\n✅ {[r[1] for r in result]} ")
    return [r[1] for r in result]


# === HELPERS ===
def to_caption(name):
    return name.replace('_', ' ').title()

def to_camel_case(name):
    parts = name.lower().split('_')
    return parts[0] + ''.join(x.capitalize() for x in parts[1:])

def get_f_data_type(sql_type, col_name):
    if 'DATE' in col_name.upper():
        return 5
    sql_type = sql_type.upper()
    if sql_type == 'TEXT':
        return 1
    elif sql_type == 'INTEGER':
        return 2
    elif sql_type == 'BIGINT':
        return 2
    elif sql_type == 'FLAT':
        return 3
    elif sql_type == 'REAL':
        return 4
    return 1

def get_f_size(sql_type, col_name):
    if 'DATE' in col_name.upper():
        return 5
    sql_type = sql_type.upper()
    if sql_type == 'TEXT':
        return 100
    elif sql_type == 'INTEGER':
        return 0
    elif sql_type == 'BIGINT':
        return 0
    elif sql_type == 'FLAT':
        return 0
    elif sql_type == 'REAL':
        return 0
    return 100

def get_f_alignment(sql_type, col_name):
    if 'DATE' in col_name.upper():
        return 5
    sql_type = sql_type.upper()
    if sql_type == 'TEXT':
        return 1
    elif sql_type == 'INTEGER':
        return 3
    elif sql_type == 'BIGINT':
        return 3
    elif sql_type == 'FLAT':
        return 3
    elif sql_type == 'REAL':
        return 3
    return 1


def matches(conn):
    matches = get_table_names(conn)
    if not matches:
        print("❌ No valid CREATE TABLE statements found.")
        exit(1)

def get_database_path():
    db_path = input("Enter the path to your SQLite database file: ").strip()
    while not os.path.isfile(db_path):
        print("File not found. Please try again.")
        db_path = input("Enter the path to your SQLite database file: ").strip()
    print(db_path)
    return db_path

def connect_to_database(db_path):
    try:
        conn = sqlite3.connect(db_path)
        print(f"\n✅ Connected to database: {db_path}")
        return conn
    except sqlite3.Error as e:
        print(f"\n❌ Error connecting to database: {e}")
        return None

def my_database_procedure(db_info):
    db_file = db_info['db']
    require_pk = db_info['pk']  # 1 or 0
    group_on = db_info['group']  # 1 or 0

    # === CONNECT TO DB ===
    conn = sqlite3.connect(ADMIN_FILE)
    cursor = conn.cursor()

    cursor.execute("UPDATE SYS_PARAMS SET F_LANGUAGE=1")
    cursor.execute("UPDATE SYS_TASKS SET F_DB_TYPE=1, F_ALIAS=?, F_NAME='demo', F_ITEM_NAME='demo'", (db_file,))
    cursor.execute("UPDATE SYS_ITEMS SET F_NAME =?, F_ITEM_NAME=?, F_JS_FILENAME=? WHERE ID=1", ('demo', 'demo', 'demo.js'))



    item_id = ITEM_START_ID
    field_id = FIELD_START_ID
    inserted_tables = []
    table_to_item_id = {}
    item_id_to_pk_field_id = {}

    # === STEP 1: Get valid tables based on --pk option ===
    all_tables = get_table_names(db_file)
    valid_tables = []

    for table_name in all_tables:
        table_info = get_table_info(db_file, table_name)
        has_id_field = any(col['col_name'].upper() == "ID" for col in table_info['fields'])

        if require_pk == 1:
            if any(col['pk'] for col in table_info['fields']):
                valid_tables.append(table_name)
            else:
                print(f"❌ Skipping table '{table_name}' — no PRIMARY KEY.")
        else:
            if has_id_field:
                valid_tables.append(table_name)
                print(f"⚠️ Including table '{table_name}' (has 'ID' column only, no PK).")
            else:
                print(f"❌ Skipping table '{table_name}' — no 'ID' column.")

    if not valid_tables:
        print("❌ No valid tables found after applying primary key rules.")
        return

    # === STEP 2: Group valid tables and create reverse mapping ===
    grouped = group_by_suffix(valid_tables)

    table_to_group_name = {table: group for group, tables in grouped.items() for table in tables}

    # === STEP 3: Insert group folders ===
    group_to_folder_id = {}
    for group_name, tables in grouped.items():
        group_folder_id = item_id
        group_to_folder_id[group_name] = group_folder_id
#        f_name = "g_" + f_name 

        cursor.execute("""
            INSERT INTO SYS_ITEMS (
                id, deleted, task_id, has_children, type_id, parent, table_id,
                f_name, f_item_name, f_table_name,
                f_visible, f_soft_delete, f_deleted_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            group_folder_id, DELETED, TASK_ID, 1, 6, 1, 0,
            group_name, "g_" + group_name.lower(), None,
            VISIBLE, None, None
        ))
        print(f"[FOLDER] Inserted Group '{group_name}' with id={group_folder_id}")
        item_id += 1
            

    # === STEP 4: Insert tables and fields ===
    for table_name in valid_tables:
        table_info = get_table_info(db_file, table_name)
        group_name = table_to_group_name.get(table_name)
        parent_id = group_to_folder_id.get(group_name)

#        print(args.group)
#        if args.group == 1:
#            parent_id = group_to_folder_id.get(group_name)
#        else:
#            parent_id = PARENT_ID
#            group_name = 'Catalogs'
#
        f_table_name = table_name
        f_item_name = table_name.lower()
        f_name = "_".join(part.capitalize() for part in table_name.replace("DEMO_", "").split("_"))

        table_item_id = item_id
        cursor.execute("""
            INSERT INTO SYS_ITEMS (
                id, deleted, task_id, type_id, parent, table_id,
                f_name, f_item_name, f_table_name,
                f_visible, f_soft_delete, f_deleted_flag, f_virtual_table, f_soft_delete
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            table_item_id, DELETED, TASK_ID, TYPE_ID, parent_id, TABLE_ID,
            f_name, f_item_name, f_table_name,
            VISIBLE, None, None, F_VIRTUAL_TABLE, F_SOFT_DELETE
        ))

        print(f"[SYS_ITEMS] Inserted table '{table_name}' under group '{group_name}' with id={table_item_id}")
        table_to_item_id[table_name] = table_item_id
        inserted_tables.append(table_name)
        item_id += 1

        # === Insert fields ===
        field_ids = []
        pk_detected = False

        for col in table_info['fields']:
            col_name = col['col_name']
            col_type = col['col_type']
            pk = col['pk']
            

            f_field_name = sanitize_field_name(to_camel_case(col_name))
            f_name = to_caption(col_name)
            f_data_type = get_f_data_type(col_type, col_name)
            f_size = get_f_size(col_type, col_name)
            f_alignment = get_f_alignment(col_type, col_name)

            cursor.execute("""
                INSERT INTO SYS_FIELDS (
                    id, owner_id, task_id, owner_rec_id, deleted,
                    f_field_name, f_db_field_name, f_name, f_data_type, f_size, f_required,
                    f_alignment, f_textarea, f_do_not_sanitize, f_calc_lookup_field
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                field_id, OWNER_ID, TASK_ID, table_item_id, DELETED,
                f_field_name, col_name, f_name, f_data_type, f_size, F_REQUIRED,
                f_alignment, F_TEXTAREA, F_DO_NOT_SANITIZE, F_CALC_LOOKUP_FIELD
            ))

            foreign_keys = get_foreign_keys(db_file, table_name)
            fk_map = {fk['from']: fk for fk in foreign_keys}
            fk = fk_map.get(col['col_name'])
            f_lookup_item = None
            f_lookup_key = None
            f_lookup_result = None            

            if fk:
                ref_table = fk['to_table']
                ref_item_id = table_to_item_id.get(ref_table)
                if ref_item_id:
                    f_lookup_item = ref_item_id
                    f_lookup_key = fk['to_column']
                    # Try to guess display column: prefer 'name', else first text field
                    ref_info = get_table_info(db_file, ref_table)
                    for ref_col in ref_info['fields']:
                        if ref_col['col_name'].lower() in ('name', 'title', 'description'):
                            f_lookup_result = ref_col['col_name']
                            break
                    if not f_lookup_result:
                        f_lookup_result = ref_info['fields'][0]['col_name']
                    print(f"🔗 Lookup detected: {table_name}.{col['col_name']} → {ref_table}.{f_lookup_key} (display {f_lookup_result})")

            if pk and not pk_detected:
                item_id_to_pk_field_id[table_item_id] = field_id
                pk_detected = True

            field_ids.append(field_id)
            field_id += 1

        # === Build F_INFO JSON ===
        view_section = [[fid, ""] for fid in field_ids]
        edit_section = [["", [[{}, [[fid] for fid in field_ids], ""]]]]
        f_info = {
            "view": {"0": ["", {}, [], {}, view_section, []]},
            "edit": {"0": ["", {}, [], edit_section]},
            "order": [],
            "reports": []
        }

        f_info_str = "json" + json.dumps(f_info)
        cursor.execute("UPDATE SYS_ITEMS SET f_info = ? WHERE id = ?", (f_info_str, table_item_id))

    # === Step 5: Update SYS_ITEMS with f_primary_key ===
    for item_id, pk_field_id in item_id_to_pk_field_id.items():
        cursor.execute("UPDATE SYS_ITEMS SET f_primary_key = ? WHERE id = ?", (pk_field_id, item_id))
        print(f"[SYS_ITEMS] Updated item_id={item_id} with f_primary_key={pk_field_id}")

# === STEP 6: Update SYS_FIELDS.F_MASTER_FIELD based on foreign keys ===

#    def get_foreign_keys(db_file, table_name):
#        cur = conn.cursor()
#        cur.execute(f"PRAGMA foreign_key_list('{table_name}')")
#        print([
#            {"from": r[3], "to_table": r[2], "to_column": r[4]}
#            for r in cur.fetchall()
#        ])
#
#        return [
#            {"from": r[3], "to_table": r[2], "to_column": r[4]}
#            for r in cur.fetchall()
#        ]

    print("\n=== STEP 6: Linking fields via F_OBJECT and F_OBJECT_FIELD (foreign keys) ===")

#    def get_foreign_keys(db_file, table_name):
#        cur = conn.cursor()
#        cur.execute(f"PRAGMA foreign_key_list('{table_name}')")
#        return [{"from": r[3], "to_table": r[2], "to_column": r[4]} for r in cur.fetchall()]
#
    for table_name, item_id in table_to_item_id.items():
        fks = get_foreign_keys(db_file, table_name)
        if not fks:
            continue

        print(f"→ Table {table_name} has {len(fks)} foreign keys")

        # Cache all fields for this table (lowercase names)
        cursor.execute("SELECT id, lower(f_db_field_name) FROM SYS_FIELDS WHERE owner_rec_id = ?", (item_id,))
        src_fields = {name: fid for fid, name in cursor.fetchall()}

        for fk in fks:
            from_field = fk["from"].lower()
            ref_table = fk["to_table"].lower()
            ref_column = fk["to_column"].lower()

            src_id = src_fields.get(from_field)
            ref_item_id = None
            ref_field_id = None

            # Find referenced SYS_ITEMS.id
            for tname, iid in table_to_item_id.items():
                if tname.lower() == ref_table:
                    ref_item_id = iid
                    break

            # Find referenced SYS_FIELDS.id
            if ref_item_id:
                cursor.execute(
                    "SELECT id FROM SYS_FIELDS WHERE owner_rec_id = ? AND lower(f_db_field_name) = ?",
                    (ref_item_id, ref_column)
                )
                row = cursor.fetchone()
                if row:
                    ref_field_id = row[0]

            if src_id and ref_item_id and ref_field_id:
                cursor.execute(
                    "UPDATE SYS_FIELDS SET F_OBJECT = ?, F_OBJECT_FIELD = ? WHERE id = ?",
                    (ref_item_id, ref_field_id, src_id)
                )
                print(f"   ✅ {table_name}.{fk['from']} → {fk['to_table']}.{fk['to_column']} | F_OBJECT={ref_item_id}, F_OBJECT_FIELD={ref_field_id}")
            else:
                print(f"   ⚠️ Skipped {table_name}.{fk['from']} → {fk['to_table']}.{fk['to_column']} (missing mapping)")

    conn.commit()
    print("✅ Step 6 complete — F_OBJECT and F_OBJECT_FIELD relationships set.")


    # === Finalize ===
    conn.commit()
    conn.close()

    print(f"\n✅ Done. Inserted {len(inserted_tables)} items and {field_id - FIELD_START_ID} fields.")

    # === Summary Group Report ===
    grouped = group_by_suffix(inserted_tables)
    print("\n📊 Grouped Inserted Tables by Meaning:\n")
    for group, tables in grouped.items():
        print(f"  • {group} ({len(tables)}): {', '.join(tables)}")

    if len(inserted_tables) > 20:
        print("\n⚠️  Since more than 20 imported tables, consider adding to CSS:\n")
        print (f"   .navbar-nav {{ flex-wrap: wrap; }}👈\n")    


def main():
    global args  # Declare it global so it modifies the outer 'args'
    parser = argparse.ArgumentParser(
        description="""Install jam.py-v7 and create a new project with jam-project.py!

        Then run this script to connect to a SQLite database, list its tables, 
        and scaffold Jam.py V7 front-end.""",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--db', required=True, help='Database name')
    parser.add_argument('--prefix', default='',  help='Tables name prefix to remove for Captions')
    parser.add_argument('--pk', default=1,  help='Require primary key: 1=yes (default), 0=allow tables without PK')
    parser.add_argument('--group', default=1,  help='Tables grouping: 1=yes (default), 0=tables into Catalogs')

    args = parser.parse_args()

    db_info = vars(args)

    connection = connect_to_database(args.db)
    if connection:
        my_database_procedure(db_info)  # 👈 Call your function here
        connection.close()

if __name__ == "__main__":
    main()	
