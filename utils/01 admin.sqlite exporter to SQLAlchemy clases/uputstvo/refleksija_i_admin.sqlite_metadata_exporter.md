
# Refleksija i admin metadata eksporter

Kada sam gore pomenuo **`Base.metadata.reflect()`**, to se odnosilo na **drugi način** da se iz postojeće baze (kao što je tvoj `admin.sqlite`) automatski generiše ORM model u SQLAlchemy-ju, bez ručnog pisanja klasa.

## Šta je `Base.metadata.reflect()`

To je metoda SQLAlchemy-jevog `metadata sistema` koja “pogleda” stvarnu bazu i napuni `MetaData` objekt informacijama o tabelama, kolonama, FK-ovima itd.

U praksi to izgleda ovako:

```py
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import declarative_base

engine = create_engine("sqlite:///admin.sqlite")
Base = declarative_base()
Base.metadata.reflect(bind=engine)
```

Posle ovoga `Base.metadata.tables` sadrži sve tabele iz baze (kao `Table` objekte).

## Šta se time dobija

- Automatska introspekcija — ne moraš pisati ORM klase ručno (kao što je radio tvoj exporter).

- Možeš "vezati” postojeću bazu za ORM odmah, npr.:

  ```py
  class SysItems(Base):
      __table__ = Base.metadata.tables['SYS_ITEMS']
  ```

  Time `SysItems` postaje “živa” ORM klasa, i odmah možeš raditi:

  ```py
  session.query(SysItems).filter_by(DELETED=0).all()
  ```

- Tako možeš koristiti postojeći `admin.sqlite` direktno u Python-u bez ručno generisanih modela — kao da imaš ORM iz koda, ali sve dolazi iz refleksije baze.

## A šta bi ti konkretno s tim?

U tvom kontekstu `admin_sqlite_exporter`-a imaš dve realne mogućnosti:

- **Koristiti `reflect()` da proveriš i validiraš exporter**:

  Tvoj exporter već generiše `.py` fajlove sa ORM klasama. Ali, možeš dodati deo koda koji koristi `Base.metadata.reflect()` da pročita postojeću bazu i proveri da li se klase i stvarne tabele poklapaju.
  
  Praktični mini-test:
  
  ```py
  for table_name in Base.metadata.tables:
      if not hasattr(models, table_name.lower()):
          print(f"Nedostaje klasa za tabelu {table_name}")
  ```

  Tako možeš automatski uhvatiti ako exporter nešto preskoči.

- **Potpuno zameniti exporter refleksijom**

  Ako ti nije bitno da imaš fizičke `.py` fajlove za svaku SYS_ tabelu, možeš `reflect()` koristiti da napraviš ORM sloj u runtime-u.
  
  Primer:
  
  ```py
  Base = declarative_base()
  Base.metadata.reflect(bind=engine)
  
  Session = sessionmaker(bind=engine)
  session = Session()
  
  SysParams = Base.metadata.tables['SYS_PARAMS']
  rows = session.execute(SysParams.select()).fetchall()
  ```

  Ovo radi čak i bez deklarisanih klasa — jer SQLAlchemy zna sve o tabelama.

## Ukratko

| Pitanje                            | Odgovor
| ---------------------------------- |----------------------------------
| Šta radi `Base.metadata.reflect()` | Učitava strukturu baze (tabele, kolone, veze) direktno u ORM metapodatke
| Na šta se to odnosi                | Na tvoj `admin.sqlite` – dakle Jam.py sistemske tabele (`SYS_ITEMS`, `SYS_FIELDS`, … )
| Šta bi s tim mogao                 | 1️. proveriti da li tvoj exporter daje ispravne klase,  2️. ili potpuno preskočiti exporter i raditi sa refleksijom u runtime-u.

## Primer: Ručno vs refleksija

Minimalni, ali moćan primer — kako bi tvoj `admin.sqlite exporter` mogao da izgleda ako koristi `Base.metadata.reflect()` umesto ručnog mapiranja.

Dakle, umesto da pišemo po jednu klasu za svaku SYS_ tabelu, ovaj pristup sam učita strukturu baze i stvori ORM klase “u letu”.

- **`admin_reflect_demo.py`**

  ```py
  from sqlalchemy import create_engine, MetaData
  from sqlalchemy.orm import declarative_base, Session
  
  DB_PATH = "exporter/admin.sqlite"
  
  # Kreiramo engine i osnovu za ORM
  engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
  Base = declarative_base()
  
  # Reflektujemo sve tabele iz baze
  Base.metadata.reflect(bind=engine)
  print(f"✅ Reflektovano {len(Base.metadata.tables)} tabela iz {DB_PATH}\n")
  
  # (Opcionalno) napravimo ORM klase dinamički
  # Svaka SYS_ tabela postaje klasa u runtime-u
  models = {}
  for table_name, table_obj in Base.metadata.tables.items():
      class_name = table_name.title().replace("_", "")
      models[class_name] = type(class_name, (Base,), {"__table__": table_obj})
      print(f"📦 Klasa {class_name} vezana za tabelu {table_name}")
  
  # Test: čitanje iz jedne tabele
  with Session(engine) as session:
      SysItems = models.get("Sysitems")  # SYS_ITEMS
      if SysItems:
          rows = session.query(SysItems).limit(5).all()
          print(f"\n SYS_ITEMS (5 redova):")
          for r in rows:
              print(f"  → {r.ID}: {r.F_NAME} ({r.F_TABLE_NAME})")
  ```

- **Šta se ovde dešava**

  - **`Base.metadata.reflect()`** pročita kompletno `admin.sqlite` — tabele, kolone, tipove, ključeve.
  - Umesto da ih pišemo ručno (kao u exporteru), mi dinamički kreiramo klase pomoću `type()`.
  - Svaka SYS_ tabela (`SYS_ITEMS`, `SYS_FIELDS`, `SYS_PARAMS`, …) postaje ORM klasa (`Sysitems`, `Sysfields`, `Sysparams`).
  - Sve radi bez ikakvog pisanog model koda.
  
- **Kako da testiraš**

  Samo pokreni:
  
  ```sh
  python admin_reflect_demo.py
  ```
  
  I trebalo bi da dobiješ nešto tipa:
  
  ```sh
  Reflektovano 12 tabela iz exporter/admin.sqlite
  
  Klasa SysItems vezana za tabelu SYS_ITEMS
  Klasa SysFields vezana za tabelu SYS_FIELDS
  ...
  
  SYS_ITEMS (5 redova):
    → 1: Task (SYS_TASKS)
    → 2: Field (SYS_FIELDS)
    → 3: User (SYS_USERS)
  ```

## Poređenje sa exporterom

| Osobina        | Klasični exporter                 | Reflect varijanta
| -------------- | --------------------------------- | -------------------------------
| Broj fajlova   | 1 po tabeli                       | samo jedan
| Generisanje    | iz SQLite schema introspekcije    | iz SQLAlchemy refleksije
| Tipovi polja   | ručno dodeljeni                   | čitaju se iz baze
| Brzina         | brže pri prvom runu, ali statički | sporije prvi put, ali dinamično
| Upotreba u Jam | iste klase, isti session API      | iste

- **Kad koristiš ovaj pristup**

Ovo je fantastično kad:

- često menjaš `admin.sqlite` (dodaješ SYS_* tabele ili kolone),
- ne želiš ručno regenerisanje `.py` fajlova svaki put,
- želiš da eksperimentišeš s ORM-om nad stvarnim Jam.py metamodelom.

## Refleksije u SQLAlchemy-ju

Refleksije nisu besplatne u Pythonu (a pogotovo ne u SQLAlchemy-ju).

Ali hajde da to raščlanimo precizno, jer ima dve vrste “sporosti” i nisu sve iste — `refleksija` u SQLAlchemy-ju nije isto što i `runtime type assertion`.

`Base.metadata.reflect(bind=engine)` radi jednokratnu introspekciju baze:

- pošalje nekoliko `PRAGMA` (u SQLite-u) ili `INFORMATION_SCHEMA` upita (u drugim bazama),
- učita nazive tabela, kolona, indekse, FK-ove i tipove,
- popuni `MetaData` objekte.

**Trajanje**: obično između 50 ms i 300 ms, čak i za 50–100 tabela.
Znači, nije “sporo” u smislu performansi aplikacije — sporo je samo *kao korak inicijalizacije*.
(Pravo usko grlo dolazi ako to pozivaš više puta u petlji.)

**Zato se reflektuje samo jednom** — i posle radiš sa keširanim metapodacima u memoriji.

### Type assertions i dinamičke klase

Ono na šta verovatno misliš kad kažeš “type assertion” su Python-ove runtime konstrukcije tipa:

```py
MyClass = type("MyClass", (Base,), {"__table__": table})
```

Ili ako se koristi `getattr`, `setattr`, `isinstance`, `hasattr` svuda po kodu.

Ta vrsta refleksije jeste:

- **spora po jedinici poziva** (jer ide kroz interpreter, ne kroz mašinski kod),
- i često **neke vrste statičkih analiza i keširanja izbegava**.

Ali i ona postaje značajna tek ako to radiš hiljadama puta — što u exporteru ne radiš.
Ona se dešava jednom po tabeli, i ostaje u memoriji dok program traje.

### Ukratko o refleksijama

| Vrsta refleksije                                     | Kada se dešava             | Tipično trajanje   | Ima li realnog uticaja
| ---------------------------------------------------- | -------------------------- | ------------------ | ----------------------
| SQLAlchemy `metadata.reflect()`                      | jednom prilikom pokretanja | ~0.1–0.3 s         | minimalan
| Dinamičko kreiranje klasa (`type()`)                 | jednom po tabeli           | mikrosekunde       | zanemarljivo
| “Type assertion” (svaki poziv, runtime provere tipa) | stalno                     | kumulativno veliko | treba izbegavati

### Zaključak za tvoj slučaj

- Refleksija SQLAlchemy-ja je **spora samo prvi put**, i samo ako ima mnogo tabela.
  (Za `admin.sqlite` — zanemarljivo.)
- Dinamičko kreiranje klasa (`type()`) koje radi naš demo je **u potpunosti bezbedno i brzo**.
- “Type assertion” u smislu proveravanja tipova u petlji — toga ovde nema.

**Zato**: ako koristiš refleksiju za generisanje modela pri startu (npr. kao deo setup-a scaffolding-a), to je savršeno prihvatljivo.

Ako bi to radio u runtime-u za svaku operaciju, onda bi to bilo loše.

**Kako da keširaš reflektovane tabele** (npr. da se čuvaju u `.json` metapodacima, pa da se sledeći put refleksija preskoči) — to je zgodan trik koji Jam-py interno ne koristi, ali bi tebi dao ubrzanje startup-a.
