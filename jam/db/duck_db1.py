import duckdb

from .duck_db import DuckDB, SafeDuckDBConnection
from .db import AbstractDB

class DuckDB1(DuckDB):
    def __init__(self):
        DuckDB.__init__(self)

    def connect(self, db_info):
        if not db_info.database:
            raise Exception('Must supply database name')
        raw_conn = duckdb.connect(db_info.database)
        return SafeDuckDBConnection(raw_conn)

db = DuckDB1()
