from ..common import consts
from .db import AbstractDB

class SafeDuckDBConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

class DuckDB(AbstractDB):
    def __init__(self):
        AbstractDB.__init__(self)
        self.db_type = consts.DUCKDB 
        self.DDL_ROLLBACK = False
        self.IS_DISTINCT_FROM = 'NOT %s IS %s'
        self.FIELD_TYPES = {
            consts.INTEGER: 'INTEGER',
            consts.TEXT: 'TEXT',
            consts.FLOAT: 'REAL',
            consts.CURRENCY: 'REAL',
            consts.DATE: 'DATE',
            consts.DATETIME: 'TIMESTAMP',
            consts.BOOLEAN: 'INTEGER',
            consts.LONGTEXT: 'TEXT',
            consts.KEYS: 'TEXT',
            consts.FILE: 'TEXT',
            consts.IMAGE: 'TEXT'
        }

    def get_params(self, lib):
        params = self.params
        params['name'] = 'DUCKDB'
        params['lib'] = ['file', 'parquet', 'httpfs' ]
        if lib == 1:
            params['database'] = True
        if lib == 2:
            params['database'] = True
        return params

    def get_select(self, query, fields_clause, from_clause, where_clause, group_clause, order_clause, fields):
        start = fields_clause
        end = ''.join([from_clause, where_clause, group_clause, order_clause])
        offset = query.offset
        limit = query.limit
        result = 'SELECT %s FROM %s' % (start, end)
        if limit:
            result += ' LIMIT %d OFFSET %d' % (limit, offset)
        return result

    def create_table(self, table_name, fields, gen_name=None, foreign_fields=None):
        sql = ''
        seq_name = gen_name if gen_name else '%s_id_seq' % table_name
        
        sql += 'CREATE SEQUENCE IF NOT EXISTS "%s" START 1;\n' % seq_name
        sql += 'CREATE TABLE "%s"\n(\n' % table_name
        lines = []
        for field in fields:
            default_text = self.default_text(field)
            if field.primary_key:
                field_type = 'INTEGER PRIMARY KEY DEFAULT nextval(\'%s\')' % seq_name
            else:
                field_type = self.FIELD_TYPES[field.data_type]
            line = '"%s" %s' % (field.field_name, field_type)
            if not default_text is None:
                line += ' DEFAULT %s' % default_text
            lines.append(line)
        sql += ',\n'.join(lines)
        sql += ')\n'
        return sql

    def insert_query(self, pk_field):
        return 'INSERT INTO "%s" (%s) VALUES (%s) RETURNING ' + pk_field.db_field_name
        
    def next_sequence(self, gen_name):
        return 'SELECT nextval(\'%s\')' % gen_name

    def after_insert(self, cursor, pk_field):
        if pk_field and not pk_field.data:
            try:
                row = cursor.fetchone()
                if row:
                    pk_field.data = row[0]
            except Exception:
                pass

    def add_field(self, table_name, field):
        default_text = self.default_text(field)
        result = 'ALTER TABLE "%s" ADD COLUMN "%s" %s' % \
            (table_name, field.field_name, self.FIELD_TYPES[field.data_type])
        if not default_text is None:
            result += ' DEFAULT %s' % default_text
        return result

    def del_field(self, table_name, field):
        return 'ALTER TABLE "%s" DROP COLUMN "%s"' % (table_name, field.field_name)

    def change_field(self, table_name, old_field, new_field):
        return ''

    def drop_table(self, table_name, gen_name):
        return 'DROP TABLE IF EXISTS "%s"' % table_name

    def set_foreign_keys(self, value):
        if value:
            return 'PRAGMA foreign_keys=on'
        else:
            return 'PRAGMA foreign_keys=off'

    def create_index(self, index_name, table_name, unique, fields, desc):
        #return 'CREATE %s INDEX "%s" ON "%s" (%s)' % (unique, index_name, table_name, fields)
        return 'CREATE %s INDEX IF NOT EXISTS "%s" ON "%s" (%s)' % (
            unique,
            index_name,
            table_name,
            fields
        )

    def drop_index(self, table_name, index_name):
        return 'DROP INDEX IF EXISTS "%s"' % index_name

    def identifier_case(self, name):
        return name.lower()

    def get_table_names(self, connection):
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM sqlite_master WHERE type='table'")
        result = cursor.fetchall()
        return [r[1] for r in result]

    def get_table_info(self, connection, table_name, db_name):
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info('%s')" % table_name)
        result = cursor.fetchall()
        fields = []
        for r in result:
            fields.append({
                'field_name': r[1],
                'data_type': r[2],
                'size': 0,
                'default_value': r[4],
                'pk': r[5]==1
            })
        return {'fields': fields, 'field_types': self.FIELD_TYPES}

db = DuckDB()