
# Universal Smart Sync v3.1 for Neo4j

Uključuje:

- SQLite / CSV / JSON / API to Neo4j
- heurističko prepoznavanje join tabela,
- relacije sa property kolonama,
- hash diff-sync,
- DRY-RUN i
- čišćenje čvorova - duhova.

> [!Note]  
> Instalacija (jednom):
>
> ```sh
> pip install neo4j pandas requests
> ```
>
> Pokretanje:
>
> - Sačuvaj skriptu kao `universal_smart_sync_v3_1.py`
> - U dnu fajla izaberi izvor (otkomentariši jednu liniju)
>
> ```sh
> `python universal_smart_sync_v3_1.py`
> ```

## `universal_smart_sync_v3_1.py`

```python
import sqlite3
from neo4j import GraphDatabase
import pandas as pd
import hashlib, json, requests, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# =========================
# CONFIG
# =========================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "test")

SYNC_LOG_FILE = Path("sync_log.json")

# True = simulacija (NE PIŠE u Neo4j / log); False = piše promene
DRY_RUN = True

# Boje za lepši log (on/off)
USE_COLOR = True


# =========================
# UTIL: boje & ispisi
# =========================
def c(code, s):
    if not USE_COLOR:
        return s
    return f"\033[{code}m{s}\033[0m"

def info(msg):  print(c("36", f"[i] {msg}"))
def ok(msg):    print(c("32", f"[✓] {msg}"))
def warn(msg):  print(c("33", f"[!] {msg}"))
def err(msg):   print(c("31", f"[x] {msg}"))


# =========================
# DATA SOURCE ADAPTERS
# =========================
def load_sqlite_dataset(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    dataset = {}
    for t in tables:
        df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
        dataset[t] = df.to_dict(orient="records")
    ok(f"SQLite učitan ({db_path}) sa {len(dataset)} tabela.")
    return dataset

def load_csv_dataset(csv_dir):
    dataset = {}
    for f in Path(csv_dir).glob("*.csv"):
        table = f.stem
        df = pd.read_csv(f)
        dataset[table] = df.to_dict(orient="records")
    ok(f"CSV folder '{csv_dir}' učitan sa {len(dataset)} tabela.")
    return dataset

def load_json_dataset(json_path):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    ok(f"JSON '{json_path}' učitan sa {len(data)} tabela.")
    return data

def load_api_dataset(api_url):
    r = requests.get(api_url, timeout=60)
    r.raise_for_status()
    data = r.json()
    ok(f"API '{api_url}' učitan sa {len(data)} tabela.")
    return data


# =========================
# SYNC UTILS
# =========================
def make_hash(row):
    # stabilan hash nad svim ključevima (None -> "")
    row_str = "|".join(f"{k}:{'' if row[k] is None else row[k]}" for k in sorted(row))
    return hashlib.md5(row_str.encode()).hexdigest()

def make_rel_hash(a_id, b_id, props_dict):
    # hash za relaciju (krajevi + props) – koristi se samo za DRY dif log
    base = f"a:{a_id}|b:{b_id}|" + "|".join(f"{k}:{props_dict.get(k)}" for k in sorted(props_dict))
    return hashlib.md5(base.encode()).hexdigest()

def load_sync_log():
    if SYNC_LOG_FILE.exists():
        try:
            return json.loads(SYNC_LOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}

def save_sync_log(data):
    SYNC_LOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def log_sync_time(sync_data, table):
    sync_data[table] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def guess_relation_name(from_col, to_table):
    base = str(from_col).lower()
    to = str(to_table).lower()
    if base.endswith("_id"):
        base = base[:-3]
    return f"{base.upper()}_REL_{to.upper()}"

def title_label(name: str) -> str:
    # Label iz imena tabele: account_user -> Account_user (jednostavno)
    if not name:
        return "X"
    return name[0].upper() + name[1:]


# =========================================================
# HEURISTIČKO PREPOZNAVANJE FK I JOIN TABELA (CSV/JSON/API)
# =========================================================
def detect_fk_columns(table, rows):
    """Vraća listu kolona koje izgledaju kao FK: *_id."""
    if not rows:
        return []
    # sve kolone zajedno iz svih redova (za slučaj nested/različite ključeve)
    keys = set().union(*(r.keys() for r in rows))
    return [k for k in keys if k.endswith("_id")]

def is_join_table_heuristic(table, rows, dataset):
    """
    Join tabela ako:
      - ima TAČNO 2 *_id kolone
      - i obe bazne tabele postoje u datasetu
    """
    fks = detect_fk_columns(table, rows)
    if len(fks) != 2:
        return False, []
    base1 = fks[0][:-3]
    base2 = fks[1][:-3]
    if base1 in dataset and base2 in dataset:
        return True, fks
    return False, fks

def extra_rel_props(table, rows, fk_cols):
    """Kolone koje nisu FK – postaju properties relacije (ako postoje)."""
    if not rows:
        return []
    keys = set().union(*(r.keys() for r in rows))
    return [k for k in keys if k not in fk_cols]


# =========================
# SMART SYNC ENGINE
# =========================
def smart_sync(dataset, driver):
    with driver.session() as session:
        stats_nodes = defaultdict(lambda: {"new": 0, "updated": 0, "deleted": 0})
        stats_rels  = defaultdict(int)
        sync_data   = load_sync_log()
        all_existing_nodes = set()

        tables = list(dataset.keys())
        info(f"Pronađeno tabela: {len(tables)}")

        # 0) pre-calc join tabele da ih preskočimo kao čvorove
        join_tables = {}
        for t in tables:
            is_join, fks = is_join_table_heuristic(t, dataset[t], dataset)
            if is_join:
                join_tables[t] = fks
        if join_tables:
            info("Join tabele (heuristika): " + ", ".join(join_tables.keys()))

        # 1) NODES (INSERT/UPDATE) – skip join tables
        print(c("1;44", "\n=== NODE SYNC ==="))
        for table in tables:
            # skip čiste join tabele (ne pravimo čvorove)
            if table in join_tables:
                info(f"Preskačem čvorove za join tabelu '{table}'")
                log_sync_time(sync_data, table)
                continue

            rows = dataset[table]
            for row in rows:
                if "id" not in row:
                    warn(f"{table}: red bez 'id' – preskačem: {row}")
                    continue

                row_hash = make_hash(row)
                row["_hash"] = row_hash
                all_existing_nodes.add((table, row["id"]))

                res = session.run(
                    f"MATCH (n:{title_label(table)} {{id: $id}}) RETURN n._hash AS h",
                    id=row["id"]
                ).single()

                if res and res["h"] == row_hash:
                    # nema promene
                    continue

                if res:
                    stats_nodes[table]["updated"] += 1
                    print(c("36", f"& UPDATE  → {table} id={row['id']}"))
                else:
                    stats_nodes[table]["new"] += 1
                    print(c("32", f"+ INSERT  → {table} id={row['id']}"))

                if not DRY_RUN:
                    props = ", ".join(f"n.{k} = ${k}" for k in row.keys())
                    cypher = f"""
                    MERGE (n:{title_label(table)} {{id: $id}})
                    ON CREATE SET {props}, n.tip = '{table}'
                    ON MATCH SET {props}
                    """
                    session.run(cypher, **row)

            log_sync_time(sync_data, table)

        # 2) RELATIONSHIPS
        print(c("1;44", "\n=== RELATION SYNC ==="))
        for table in tables:
            rows = dataset[table]

            # (A) JOIN TABELA ⇒ direktne relacije (sa props ako ima extra kolona)
            if table in join_tables:
                fk1, fk2 = join_tables[table]
                base1, base2 = fk1[:-3], fk2[:-3]
                rel_name = f"{base1.upper()}_{base2.upper()}_REL"
                props_cols = extra_rel_props(table, rows, [fk1, fk2])

                info(f"{table}: join → {base1} ⇢ {base2} [{rel_name}] (props={bool(props_cols)})")

                for row in rows:
                    a_id = row.get(fk1)
                    b_id = row.get(fk2)
                    if a_id is None or b_id is None:
                        continue

                    params = {"a_id": a_id, "b_id": b_id}
                    props_set = ""
                    if props_cols:
                        for p in props_cols:
                            params[p] = row.get(p, None)
                        props_set = " {" + ", ".join(f"{p}: ${p}" for p in props_cols) + "}"

                    stats_rels[rel_name] += 1
                    print(c("35", f"MERGE rel  → {base1}({a_id}) -[{rel_name}{' props' if props_cols else ''}]-> {base2}({b_id})"))

                    if not DRY_RUN:
                        cypher = f"""
                        MATCH (a:{title_label(base1)} {{id: $a_id}}),
                              (b:{title_label(base2)} {{id: $b_id}})
                        MERGE (a)-[r:{rel_name}]->(b)
                        {"SET " + ", ".join(f"r.{p} = ${p}" for p in props_cols) if props_cols else ""}
                        """
                        session.run(cypher, **params)

                continue  # idući table

            # (B) Regularne FK relacije – svaka *_id kolona vezuje na {base}.id ako takva tabela postoji
            fk_cols = detect_fk_columns(table, rows)
            for fk in fk_cols:
                ref = fk[:-3]
                if ref not in dataset:
                    continue  # nema ciljane tabele u datasetu → preskoči

                rel_name = guess_relation_name(fk, ref)
                info(f"{table}.{fk} -> {ref}.id  [{rel_name}]")

                # nema “props” – ovo su obične 1:N veze
                if not DRY_RUN:
                    cypher = f"""
                    MATCH (a:{title_label(table)}), (b:{title_label(ref)})
                    WHERE a.{fk} = b.id
                    MERGE (a)-[:{rel_name}]->(b)
                    """
                    session.run(cypher)
                # statistika (približno – bez brojanja po redovima radi brzine)
                stats_rels[rel_name] += len(rows) if rows else 0

        # 3) DELETE “duhova” (čvorovi koji više ne postoje u izvoru)
        print(c("1;44", "\n=== CLEANUP ==="))
        for table in tables:
            if table in join_tables:
                continue  # join tabele ne generišu čvorove

            ids_src = [i for (t, i) in all_existing_nodes if t == table]
            res = session.run(
                f"MATCH (n:{title_label(table)}) RETURN collect(n.id) AS ids"
            ).single()
            ids_neo = res["ids"] if res and res["ids"] else []
            to_delete = [i for i in ids_neo if i not in ids_src]

            if to_delete:
                stats_nodes[table]["deleted"] += len(to_delete)
                for i in to_delete:
                    print(c("31", f"× DELETE  → {table} id={i}"))
                if not DRY_RUN:
                    session.run(
                        f"MATCH (n:{title_label(table)}) WHERE n.id IN $ids DETACH DELETE n",
                        ids=to_delete,
                    )

        # 4) META TAGS & LOG
        if not DRY_RUN:
            # meta: broj veza po čvoru
            session.run("""
                MATCH (n)
                OPTIONAL MATCH (n)-[r]-()
                WITH n, count(r) AS broj_veza
                SET n.count_of_rel = broj_veza
            """)
            save_sync_log(sync_data)
            ok("Sinhronizacija upisana i meta tagovi ažurirani.")
        else:
            warn("DRY-RUN je uključen: Neo4j i sync log NISU menjani.")

        # 5) REZIME
        print(c("1;44", "\n=== REZIME ==="))
        total_new = total_upd = total_del = 0
        for t, s in stats_nodes.items():
            n, u, d = s["new"], s["updated"], s["deleted"]
            if n or u or d:
                print(f"{title_label(t):18} →  + {n:3}  & {u:3}  × {d:3}")
            total_new += n; total_upd += u; total_del += d
        print(f"\nČVOROVI  →  + {total_new}  & {total_upd}  × {total_del}")

        if stats_rels:
            print("\nVEZE:")
            for rname, cnt in stats_rels.items():
                print(f"  {rname:28} ~ {cnt}")
        print("\n✅ Universal Smart Diff Sync v3.1 završeno.\n")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    # === IZABERI IZVOR (otkomentariši jednu liniju) ===
    # dataset = load_sqlite_dataset("primer.db")
    # dataset = load_csv_dataset("data/")          # npr. data/person.csv, data/project.csv, data/person_project.csv
    # dataset = load_json_dataset("data.json")     # JSON: { "person":[...], "project":[...], "person_project":[...] }
    # dataset = load_api_dataset("https://example.com/api/export")

    # Primer: SQLite
    dataset = load_sqlite_dataset("primer.db")

    smart_sync(dataset, driver)
```

## Kako radi heuristika za CSV/JSON/API

- **Join tabela**: ako tabela ima tačno dve kolone koje se završavaju  
  na `_id`** i obe njihove bazne tabele postoje u datasetu → tretira se kao agregacija.
  - Ako ima **samo ta dva FK** → pravi se **relacija bez props**.
  - Ako ima **još kolona** → te kolone postaju **properties relacije**.

- **Regularan FK (1:N)**: svaka kolona `*_id` pravi MERGE ka tabeli `  
  {base}.id`, ako ta tabela postoji.
- **Čvorovi se ne prave** za join tabele (čiste ili sa props).
