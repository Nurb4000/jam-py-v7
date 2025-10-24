
# Jampy app scaffold

`scaffold_common.py` je dizajniran da bude baza za sve tvoje buduće `scaffold_{driver}.py` module (SQLite, MySQL, PostgreSQL, itd.).

## `scaffold_common.py`

Zajedničke funkcije i konstante za sve Jam.py scaffold_{driver} module.

### Kako ga koristiš

U svakom `scaffold_{driver}.py` (recimo `scaffold_sqlite3.py`) samo na vrhu dodaš:

```python
import scaffold_common as common
```

I onda sve svoje stare pozive zameniš ovako:

```python
field = common.build_field_record(...)
item = common.build_item_record(...)
dtype = common.get_f_data_type(sql_type)
```

To znači da:

- nema više duplog koda između SQLite i ostalih verzija,
- sve pomoćne funkcije i konstante su centralizovane,
- lako dodaješ novi `scaffold_postgres.py` bez kopiranja logike.

## SQLite Jampy app scaffolding

Koristi `scaffold_common.py` kao zajedničku bazu.

Ovaj fajl je potpuno funkcionalan, ali daleko čistiji od originala - uklonjeni su svi duplikati, a sve pomoćne funkcije i konstante su povučene iz `scaffold_common.py`.

Sav kod se nalazi u `scaffold_sqlite3.py`].

## Firebird Jampy app scaffolding

Napravljen po istom modelu kao `scaffold_sqlite3.py`, i naravno koristi isti `scaffold_common.py`.

Sav kod se nalazi u `scaffold_firebird.py`.

## MySQL Jampy app scaffolding

Napravljen po istom modelu kao `scaffold_sqlite3.py`, i naravno koristi isti `scaffold_common.py`.

Sav kod se nalazi u `scaffold_mysql.py`.

## Postgres Jampy app scaffolding

Napravljen po istom modelu kao `scaffold_sqlite3.py`, i naravno koristi isti `scaffold_common.py`.

Sav kod se nalazi u `scaffold_postgres.py`.

### Šta je urađeno

|Deo             | Staro stanje               | Novo stanje         |
| -------------- | -------------------------- | ------------------- |
| Helperi (`to_camel_case`, `sanitize_field_name`, `get_f_data_type`, …) | duplirani u više fajlova | svi prebačeni u `scaffold_common.py` |
| Konstante (`ITEM_START_ID`, `FIELD_START_ID`, …) | definisane u svakom modulu | centralizovane |
| Logika upisa u `admin.sqlite` | duža i ponavljana | generička funkcija `write_to_admin()` |
| Reusability | teško dodati novi DB | sada se samo zameni `get_table_info()` i `connect_to_database()` |

## `scaffold_loader.py`

Evo i poslednjeg dela slagalice — **`scaffold_loader.py`**, univerzalni “registry” koji automatski detektuje drajver i pokreće pravi `scaffold_{driver}.py` modul.

Sav kod se nalazi u `scaffold_loader.py`.

## Kako radi

- Uzme `driver` iz `db_info` (`sqlite`, `mysql`, `postgres`,
  `firebird`).
- Importuje odgovarajući modul (`scaffold_sqlite3`, `scaffold_mysql`,
  `scaffold_postgres`, `scaffold_firebird`).
- Pozove:
  - `connect_to_database(db_info)`
  - `my_database_procedure(conn, db_info)`

- Zatvori konekciju i odštampa uredne debug poruke.

---

## Kompletan sistem

```sh
scaffold_common.py
scaffold_sqlite3.py
scaffold_mysql.py
scaffold_postgres.py
scaffold_firebird.py
scaffold_loader.py
```

Svi zajedno čine "univerzalni Jam.py scaffold" engine koji može da pročita bilo koju od `SQLIte3`, `Firebird`, `MyQSL` i `PostgreSQL` bazu i napuni `admin.sqlite` bez da se išta menja u kodu.

Sve centralizovano, modularno i skalabilno (MS SQL Server i Oracle).
