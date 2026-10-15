try:
    import pyodbc
except ImportError as e:
    if 'libodbc.so' in str(e):
        raise ImportError(
            'The Access database support is only for Windows.'
        ) from e
    raise
import datetime

from ..common import consts
from .db import AbstractDB

drivers = pyodbc.drivers()
#print(drivers)


class AccessDB(AbstractDB):
    def __init__(self):
        AbstractDB.__init__(self)
        self.db_type = consts.ACCESS
        self.IS_DISTINCT_FROM = 'NOT %s IS %s'
        self.FIELD_TYPES = {
            consts.INTEGER: 'INTEGER',
            consts.TEXT: 'TEXT',
            consts.FLOAT: 'REAL',
            consts.CURRENCY: 'REAL',
            consts.DATE: 'TEXT',
            consts.DATETIME: 'TEXT',
            consts.BOOLEAN: 'INTEGER',
            consts.LONGTEXT: 'TEXT',
            consts.KEYS: 'TEXT',
            consts.FILE: 'TEXT',
            consts.IMAGE: 'TEXT'
        }

    def access_driver_installed():
        return any("Microsoft Access Driver" in d for d in pyodbc.drivers())
        #print(access_driver_installed())

    def get_params(self, lib):
        params = self.params
        params['name'] = 'ACCESS'
        return params

    def access_upper(self, value):
        try:
            return value.upper()
        except:
            return value

    def connect(self, db_info):
        if not db_info.database:
            raise Exception('Must supply database name')
        #conn_str = (r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ="%r" %db_info.database ;')
        conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        conn_str += 'DBQ=%s' % db_info.database
        conn_str += r';)'

        #print(conn_str)
        #print(db_info.database)
        connection = pyodbc.connect(conn_str)
        #connection.create_function("UPPER", 1, self.sqlite_upper)
        cursor = connection.cursor()
        #cursor.execute("PRAGMA foreign_keys = ON")
        return connection

    def process_query_params(self, params, cursor):
        result = super().process_query_params(params, cursor)

        for i, value in enumerate(result):
            if isinstance(value, datetime.datetime):
                result[i] = value.strftime('%Y-%m-%d %H:%M:%S')

        return result

    def get_select_query(self, item, query):
        field_list = query.fields
        if len(field_list):
            fields = [item._field_by_name(name) for name in field_list]
        else:
            fields = item._fields

        fields_clause = self.fields_clause(item, query, fields)
        from_clause = self.from_clause(item, query, fields)
        where_clause, params = self.where_clause(item, query)
        group_clause = self.group_clause(item, query, fields)
        order_clause = self.order_clause(item, query)

        sql = self.get_select_with_item(
            item, query, fields_clause, from_clause,
            where_clause, group_clause, order_clause, fields
        )
        return sql, params


    def get_select_with_item(self, item, query, fields_clause,
                             from_clause, where_clause, group_clause,
                             order_clause, fields):
        offset = query.offset or 0
        limit = query.limit

        if not limit or not order_clause or (query.funcs and not query.group_by):
            end = ''.join([
                from_clause, where_clause, group_clause, order_clause
            ])
            return 'SELECT %s FROM %s' % (fields_clause, end)

#        pk_field = item._field_by_name(item._primary_key)
#        pk_expr = '%s."%s"' % (
#            self.table_alias(item),
#            pk_field.db_field_name
#        )

        pk_field = item._field_by_name(item._primary_key)

        if not pk_field:
            end = ''.join([
                from_clause, where_clause, group_clause, order_clause
            ])
            return 'SELECT %s FROM %s' % (fields_clause, end)

        pk_expr = '%s."%s"' % (
            self.table_alias(item),
            pk_field.db_field_name
        )
        order_expr = order_clause.strip()
        if order_expr[:8].upper() == 'ORDER BY':
            order_expr = order_expr[8:].strip()

        parts = order_expr.rsplit(' ', 1)
        if len(parts) == 2 and parts[1].upper() in ('ASC', 'DESC'):
            sort_expr, direction = parts[0], parts[1].upper()
        else:
            sort_expr, direction = order_expr, 'ASC'

        reverse = 'DESC' if direction == 'ASC' else 'ASC'

        keyset = """
            SELECT %s AS PageID, %s AS SortValue
            FROM %s %s
        """ % (
            pk_expr, sort_expr, from_clause, where_clause
        )

        paged_keys = """
            SELECT TOP %s PageID
            FROM (
                SELECT TOP %s PageID, SortValue
                FROM (%s) AS K
                ORDER BY SortValue %s, PageID %s
            ) AS K2
            ORDER BY SortValue %s, PageID %s
        """ % (
            limit, offset + limit, keyset,
            direction, direction,
            reverse, reverse
        )

#        if where_clause.strip():
#            page_where = '%s AND %s IN (%s)' % (
#                where_clause.strip(), pk_expr, paged_keys
#            )
#        else:
#            page_where = ' WHERE %s IN (%s)' % (pk_expr, paged_keys)
        page_where = ' WHERE %s IN (%s)' % (pk_expr, paged_keys)
        end = ''.join([
            from_clause, page_where, group_clause, order_clause
        ])
        return 'SELECT %s FROM %s' % (fields_clause, end)

        def get_fields(self, query, fields, alias):
            sql = ''
            for field in fields:
                if field.master_field:
                    pass
                else:
                    # MS Access uses brackets [] instead of quotes for field names
                    sql += '%s.[%s], ' % (alias, field.db_field_name)
            if query.expanded:
                for field in fields:
                    if field.lookup_item:
                        sql += '[%s_LOOKUP], ' % field.db_field_name
            sql = sql[:-2]
            return sql

    def get_select(self, query, fields_clause, from_clause, where_clause, group_clause, order_clause, fields):
        print("offset =", query.offset)
        print("limit =", query.limit)
        print("order_clause =", order_clause)
        print("FIELDS:", [
            (f.field_name, f.db_field_name)
            for f in fields
        ])
        print(">>> ACCESS get_select CALLED <<<", __file__)
        start = fields_clause
        end = ''.join([from_clause, where_clause, group_clause, order_clause])

        offset = query.offset
        limit = query.limit

        if not limit:
            return 'SELECT %s FROM %s' % (start, end)

        # Extract PK field and order direction separately
        #order_expr = order_clause.replace("ORDER BY", "").strip()
        # Use the actual primary key for paging, not the sort expression.
        pk_field = next(f for f in fields if f.field_name == item._primary_key)
        pk = '%s."%s"' % (
            self.table_alias(item),
            pk_field.db_field_name
        )

        # Keep the requested ordering for the paging query.
        order_expr = order_clause.replace("ORDER BY", "").strip()

        parts = order_expr.rsplit(' ', 1)

        if len(parts) == 2 and parts[1].upper() in ('ASC', 'DESC'):
            pk = parts[0]
            order_direction = parts[1]
        else:
            pk = order_expr
            order_direction = ''

        #print("pk =", pk)
        #print("direction =", order_direction)

        keyset = """
        SELECT %s AS ID
        FROM %s %s
        """ % (
            pk,
            from_clause,
            where_clause
        )

        # paged_keys = """
        # SELECT TOP %s ID
        # FROM (
        #     SELECT TOP %s ID
        #     FROM (
        #         %s
        #     ) AS K
        #     ORDER BY ID
        # ) AS K2
        # ORDER BY ID DESC
        # """ % (
        #     limit,
        #     offset + limit,
        #     keyset
        # )
        if order_direction.upper() == 'DESC':
            first_order = 'DESC'
            second_order = 'ASC'
        else:
            first_order = 'ASC'
            second_order = 'DESC'

        paged_keys = """
        SELECT TOP %s ID
        FROM (
            SELECT TOP %s ID
            FROM (
                %s
            ) AS K
            ORDER BY ID %s
        ) AS K2
        ORDER BY ID %s
        """ % (
            limit,
            offset + limit,
            keyset,
            first_order,
            second_order
        )

        result = """
        SELECT %s
        FROM %s
        INNER JOIN (
            %s
        ) AS P
        ON %s = P.ID
        %s
        """ % (
            fields_clause,
            from_clause,
            paged_keys,
            pk,
            order_clause
        )

        #print("result:", result)

        return result

  

    def convert_like(self, field_name, val, data_type):
        return '%s' % field_name, val.upper()


#    def create_table(self, table_name, fields, gen_name=None, foreign_fields=None):
#        primary_key = ''
#        sql = 'CREATE TABLE "%s"\n(\n' % table_name
#        lines = []
#        for field in fields:
#            default_text = self.default_text(field)
#            line = '"%s" %s' % (field.field_name, self.FIELD_TYPES[field.data_type])
#            if field.primary_key:
#                primary_key = field.field_name
#                line += ' PRIMARY KEY'
#            if not default_text is None:
#                line += ' DEFAULT %s' % default_text
#            lines.append(line)
#        if foreign_fields:
#            for field in foreign_fields:
#                lines.append('FOREIGN KEY(%s) REFERENCES %s(%s)\n' % \
#                    (field['key'], field['ref'], field['primary_key']))
#        sql += ',\n'.join(lines)
#        sql += '\n)'
#        return sql
    def create_table(self, table_name, fields, gen_name=None, foreign_fields=None):
        sql = 'CREATE TABLE "%s"\n(\n' % table_name
        lines = []

        for field in fields:
            default_text = self.default_text(field)

            if field.primary_key:
                line = '"%s" COUNTER CONSTRAINT PK_%s PRIMARY KEY' % (
                    field.field_name,
                    table_name
                )
            else:
                line = '"%s" %s' % (
                    field.field_name,
                    self.FIELD_TYPES[field.data_type]
                )

                if default_text is not None:
                    line += ' DEFAULT %s' % default_text

            lines.append(line)

        if foreign_fields:
            for field in foreign_fields:
                lines.append(
                    'FOREIGN KEY("%s") REFERENCES "%s"("%s")' % (
                        field['key'],
                        field['ref'],
                        field['primary_key']
                    )
                )

        sql += ',\n'.join(lines)
        sql += '\n)'

        return sql

    def add_field(self, table_name, field):
        default_text = self.default_text(field)
        result = 'ALTER TABLE "%s" ADD COLUMN "%s" %s' % \
            (table_name, field.field_name, self.FIELD_TYPES[field.data_type])
        if not default_text is None:
            result += ' DEFAULT %s' % default_text
        return result

    def del_field(self, table_name, field):
        return ''

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
        return 'CREATE %s INDEX "%s" ON "%s" (%s)' % (unique, index_name, table_name, fields)

    def drop_index(self, table_name, index_name):
        return 'DROP INDEX IF EXISTS "%s"' % index_name

    def after_insert(self, cursor, pk_field):
        if pk_field and not pk_field.data:
#            pk_field.data = cursor.lastrowid
            cursor.execute('SELECT @@IDENTITY')
            pk_field.data = cursor.fetchone()[0]

    def get_table_names(self, connection):
        cursor = connection.cursor()
        cursor.tables(tableType='TABLE')
        result = cursor.fetchall()
        return [r[2] for r in result]

    def get_table_info(self, connection, table_name, db_name):
        cursor = connection.cursor()
        cursor.columns("PRAGMA table_info('%s')" % table_name)
        cursor.columns(table = '%s' % table_name)
        result = cursor.fetchall()
        fields = []
        for r in result:
            fields.append({
                'field_name': r[3],
                'data_type': r[5],
                'size': 0,
                'default_value': r[4],
                'pk': 0
            })
        return {'fields': fields, 'field_types': self.FIELD_TYPES}

db = AccessDB()
