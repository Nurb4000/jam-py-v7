
import json
import re
import datetime

# KONSTANTE – zajedničke za sve drajvere

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

DEFAULT_GROUP = 1
DEFAULT_OWNER = 3

# JAM.PY TYPES
# TEXT, INTEGER, FLOAT, CURRENCY, DATE, DATETIME, BOOLEAN, LONGTEXT, KEYS, FILE, IMAGE = range(1, 12)

# Tipovi koji se prevode u Jam.py field_type vrednosti
TYPE_MAPPING = {
    "VARCHAR": "TEXT",
    "CHAR": "TEXT",
    "TEXT": "TEXT",
    "INTEGER": "INTEGER",
    "INT": "INTEGER",
    "SMALLINT": "INTEGER",
    "BIGINT": "INTEGER",
    "REAL": "FLOAT",
    "FLOAT": "FLOAT",
    "DOUBLE": "FLOAT",
    "DECIMAL": "CURRENCY",
    "NUMERIC": "CURRENCY",
    "DATE": "DATE",
    "DATETIME": "DATETIME",
    "TIMESTAMP": "DATETIME",
    "BOOLEAN": "BOOLEAN",
    "BLOB": "LONGTEXT"
}

# POMOĆNE FUNKCIJE – svi drajveri ih koriste

def to_camel_case(s: str) -> str:
    """Pretvara ime tabele/kolone u CamelCase."""
    return "".join(w.capitalize() for w in re.split(r"[_\W]+", s) if w)

def to_caption(s: str) -> str:
    """Kreira lep naslov iz imena kolone."""
    s = s.replace("_", " ").strip().capitalize()
    return re.sub(r"\s+", " ", s)

def sanitize_field_name(name: str) -> str:
    """Uklanja nedozvoljene karaktere iz imena kolone."""
    return re.sub(r"[^\w_]", "", name)

def get_f_data_type(col_type: str) -> str:
    """Vraća Jam.py tip podatka na osnovu SQL tipa."""
    if not col_type:
        return 'TEXT'

    base_type = col_type.upper().split('(')[0].strip()

    # grupisani SQL tipovi prema Jam.py podršci
    if base_type in ('INT', 'INTEGER', 'SMALLINT', 'BIGINT', 'BOOLEAN'):
        return 'INTEGER'
    elif base_type in ('REAL', 'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC', 'CURRENCY'):
        return 'FLOAT'
    elif base_type in ('DATE', 'DATETIME', 'TIMESTAMP'):
        return 'TEXT'  # Jam.py datume tretira kao TEXT
    elif base_type in ('BLOB', 'LONGTEXT', 'TEXT', 'CHAR', 'VARCHAR'):
        return 'TEXT'
    else:
        return 'TEXT'

def make_field_info(name: str, data_type: str, pk=False, not_null=False) -> str:
    """Generiše JSON string za SYS_FIELDS.f_info."""
    info = {
        "field_name": name,
        "data_type": data_type,
        "primary_key": bool(pk),
        "not_null": bool(not_null),
        "created_at": datetime.datetime.now().isoformat()
    }
    return json.dumps(info, ensure_ascii=False)

def debug(msg: str):
    """Lagan debug print, lako se može zameniti loggerom."""
    print(f"DEBUG: {msg}")

#  POMOĆNE STRUKTURE

def build_field_record(table_id, name, col_type, pk=False, not_null=False, field_id=None):
    """Kreira jedan red za SYS_FIELDS."""
    data_type = get_f_data_type(col_type)
    f_info = make_field_info(name, data_type, pk=pk, not_null=not_null)

    return {
        "id": field_id or None,
        "f_table": table_id,
        "f_name": sanitize_field_name(name),
        "f_caption": to_caption(name),
        "f_data_type": data_type,
        "f_not_null": int(not_null),
        "f_primary_key": int(pk),
        "f_info": f_info,
    }

def build_item_record(name, group=DEFAULT_GROUP, owner=DEFAULT_OWNER, item_id=None):
    """Kreira jedan red za SYS_ITEMS (tabelu)."""
    return {
        "id": item_id or None,
        "f_name": name,
        "f_caption": to_caption(name),
        "f_owner": owner,
        "f_group": group,
        "f_info": json.dumps({
            "table": name,
            "created_at": datetime.datetime.now().isoformat()
        }, ensure_ascii=False),
    }
