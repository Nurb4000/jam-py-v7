from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from models import Base

DB_PATH = "admin.sqlite"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)

def main():
    print("Povezujem se na:", DB_PATH)
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("\n📋 Pronađene tabele u bazi:")
    for t in tables:
        print(f"  • {t}")

    with Session(engine) as session:
        print("\n🔍 Brz pregled SYS_ tabela:")
        for cls in Base.registry.mappers:
            model = cls.class_
            table_name = model.__tablename__
            try:
                count = session.execute(select(model)).fetchall()
                print(f"  {table_name:<25} → {len(count)} redova")
            except Exception as e:
                print(f"  {table_name:<25} {e.__class__.__name__}: {e}")

    print("\nORM povezivanje završeno.")

if __name__ == "__main__":
    main()
