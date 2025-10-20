import os
import sqlite3

OUTPUT_DIR = "models"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def map_sqlite_type(sqlite_type: str):
    if not sqlite_type:
        return "String"
    t = sqlite_type.upper()
    if "INT" in t:
        return "Integer"
    if "CHAR" in t or "CLOB" in t or "TEXT" in t:
        return "String"
    if "BLOB" in t:
        return "LargeBinary"
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return "Float"
    if "DATE" in t or "TIME" in t:
        return "DateTime"
    return "String"

def export_sys_models(db_path="admin.sqlite"):
    ensure_dir(OUTPUT_DIR)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Sve SYS_ tabele iz admin.sqlite baze podataka
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'SYS_%' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]

    generated = []

    for table_name in tables:
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = cur.fetchall()
        if not columns:
            continue

        class_name = "".join([w.capitalize() for w in table_name.lower().split("_")])
        generated.append((table_name, class_name))

        lines = [
            "from sqlalchemy import String, Integer, Float, LargeBinary, DateTime, Boolean, Text",
            "from sqlalchemy.orm import Mapped, mapped_column",
            "from . import Base",
            "",
            f"class {class_name}(Base):",
            f"    __tablename__ = '{table_name}'",
            "",
        ]

        for cid, name, col_type, notnull, default_value, pk in columns:
            sa_type = map_sqlite_type(col_type)
            pk_flag = ", primary_key=True" if pk else ""
            nullable = "" if notnull else ", nullable=True"
            default = f", default={default_value}" if default_value else ""
            lines.append(f"    {name}: Mapped[{sa_type}] = mapped_column({sa_type}{pk_flag}{nullable}{default})")

        lines.append("")
        lines.append("    def __repr__(self):")
        lines.append(f"        return f\"<{class_name}(id={{getattr(self, 'ID', '?')}})>\"")
        lines.append("")

        out_path = os.path.join(OUTPUT_DIR, f"{table_name.lower()}.py")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Generisano: {out_path}")

    # --- automatski __init__.py ---
    init_lines = [
        "# Auto-generated: Import All SYS_* Models",
        "from sqlalchemy.orm import DeclarativeBase",
        "",
        "class Base(DeclarativeBase):",
        "    pass",
        "",
    ]
    for table_name, class_name in generated:
        init_lines.append(f"from .{table_name.lower()} import {class_name}")
    init_lines.append("")
    init_lines.append("__all__ = [")
    for _, class_name in generated:
        init_lines.append(f"    '{class_name}',")
    init_lines.append("]")
    init_lines.append("")

    init_path = os.path.join(OUTPUT_DIR, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write("\n".join(init_lines))

    conn.close()
    print("\n✅ Gotovo! Sve SYS_* ORM klase koriste zajednički Base iz models/__init__.py.")

if __name__ == "__main__":
    export_sys_models("admin.sqlite")