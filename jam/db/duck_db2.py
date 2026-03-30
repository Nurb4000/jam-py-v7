import os
import duckdb

from .duck_db import DuckDB, SafeDuckDBConnection
from .db import AbstractDB

class DuckDB2(DuckDB):
    def __init__(self):
        DuckDB.__init__(self)

    def connect(self, db_info):
        if not db_info.database:
            raise Exception('Must supply database name')
        raw_conn = duckdb.connect(db_info.database)

        parquet_path = db_info.database  # could be 'flights.parquet'

        if os.path.isfile(parquet_path):
            base_name = os.path.splitext(os.path.basename(parquet_path))[0]
            table_name = f"{base_name}_view"   # append _view
            raw_conn.execute(f"""
                CREATE VIEW {table_name} AS
                SELECT row_number() OVER () AS jam_id, *
                FROM read_parquet('{parquet_path}')
            """)
            _parquet_tables = [table_name]

        return SafeDuckDBConnection(raw_conn)

    def get_select(self, query, fields_clause, from_clause, where_clause, group_clause, order_clause, fields):
        start = fields_clause
        end = ''.join([from_clause, where_clause, group_clause, order_clause])
        offset = query.offset
        limit = query.limit
        result = 'SELECT %s FROM %s' % (start, end)
        if limit:
            result += ' LIMIT %d OFFSET %d' % (limit, offset)
        return result

    def get_table_names(self, connection):
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        result = cursor.fetchall()
        return [r[0] for r in result]

db = DuckDB2()
