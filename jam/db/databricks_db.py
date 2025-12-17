from databricks import sql
import re

from ..common import consts
from .db import AbstractDB

class DatabricksDB(AbstractDB):
    def __init__(self):
        AbstractDB.__init__(self)
        self.db_type = consts.DATABRICKS
        self.DDL_ROLLBACK = True
        self.DESC_NULLS = 'NULLS LAST'
        self.ASC_NULLS = 'NULLS FIRST'
        self.LIKE = 'LIKE'
        self.FIELD_TYPES = {
            consts.INTEGER: 'LONG',
            consts.TEXT: 'STRING',
            consts.FLOAT: 'NUMERIC',
            consts.CURRENCY: 'NUMERIC',
            consts.DATE: 'DATE',
            consts.DATETIME: 'TIMESTAMP',
            consts.BOOLEAN: 'INTEGER',
            consts.LONGTEXT: 'TEXT',
            consts.KEYS: 'TEXT',
            consts.FILE: 'TEXT',
            consts.IMAGE: 'TEXT'
        }
        self.catalog = None
        self.schema = None

    def get_params(self, lib):
        params = self.params
        params['name'] = 'DATABRICKS'
        params['login'] = True
        params['password'] = True
        params['encoding'] = False
        params['host'] = True
        params['port'] = True
        params['dsn'] = False
        return params

    def connect(self, db_info):
        # store for later use in SQL builders
        DatabricksDB.database = db_info.database  # THIS MUST HAPPEN

        conn = sql.connect(
            server_hostname=db_info.host,
            http_path=db_info.user,
            access_token=db_info.password,
            database=db_info.database
        )
#        print(db_info.database)
        conn.db_info = db_info
        conn.commit = lambda: None
        conn.rollback = lambda: None
        return conn



    def _get_catalog_schema(self, db_name):
        if not db_name:
            db_name = self.app.admin.task_db_info.database
        parts = db_name.split('.')
        if len(parts) == 2:
            return parts[0].lower(), parts[1].lower()
        elif len(parts) == 1:
            return None, parts[0].lower()
        return None, None

    def get_select(self, query, fields_clause, from_clause,
                   where_clause, group_clause, order_clause, fields):

        catalog, schema = self._get_catalog_schema(getattr(query, 'db_name', None))

        if fields:
            select_list = ', '.join(
                f"`{f.field_name.lower()}`" for f in fields
            )
        else:
            select_list = fields_clause

        sql = f"SELECT {select_list} FROM {from_clause}{where_clause}{group_clause}{order_clause}"

        # Normalize table/column names

        def table_repl(match):
            table = match.group(1).lower()
            if catalog and schema:
                return f"FROM `{catalog}`.`{schema}`.`{table}`"
            elif schema:
                return f"FROM `{schema}`.`{table}`"
            else:
                return f"FROM `{table}`"

        sql = re.sub(r'FROM\s+"([^"]+)"', table_repl, sql, flags=re.IGNORECASE)
        sql = re.sub(r'JOIN\s+"([^"]+)"', lambda m: table_repl(m).replace('FROM', 'JOIN'), sql, flags=re.IGNORECASE)
        sql = re.sub(r'"([^"]+)"', lambda m: f"`{m.group(1).lower()}`", sql)

        if query.limit:
            sql += f" LIMIT {query.limit} OFFSET {query.offset or 0}"

        return sql





    def value_literal(self, index):
        return '?'

    def convert_like(self, field_name, val, data_type):
        return '%s' % field_name, val.lower()


    def create_table(self, table_name, fields, gen_name=None, foreign_fields=None):
        sql = ''
        primary_key = ''
        seq_name = gen_name
        sql = 'CREATE TABLE "%s"\n(\n' % table_name
        lines = []
        for field in fields:
            default_text = self.default_text(field)
            if field.primary_key:
                field_type = 'SERIAL PRIMARY KEY'
            else:
                field_type = self.FIELD_TYPES[field.data_type]
            line = '"%s" %s' % (field.field_name, field_type)
            if not default_text is None:
                line += ' DEFAULT %s' % default_text
            lines.append(line)
        sql += ',\n'.join(lines)
        sql += ')\n'
        return sql

    def drop_table(self, table_name, gen_name):
        result = []
        result.append('DROP TABLE "%s"' % table_name)
        if gen_name:
            result.append('DROP SEQUENCE IF EXISTS "%s"' % gen_name)
        return result

    def add_field(self, table_name, field):
        default_text = self.default_text(field)
        line = 'ALTER TABLE "%s" ADD COLUMN "%s" %s' % \
            (table_name, field.field_name, self.FIELD_TYPES[field.data_type])
        if not default_text is None:
            line += ' DEFAULT %s' % default_text
        return line

    def del_field(self, table_name, field):
        return 'ALTER TABLE "%s" DROP COLUMN "%s"' % (table_name, field.field_name)

    def change_field(self, table_name, old_field, new_field):
        result = []
        default_text = self.default_text(new_field)
        field_info = self.get_field_info(old_field.field_name, table_name)
        if old_field.field_name != new_field.field_name:
            result.append('ALTER TABLE "%s" RENAME COLUMN  "%s" TO "%s"' % \
                (table_name, old_field.field_name, new_field.field_name))
        if old_field.size != new_field.size:
            if field_info['data_type'].upper() in ['CHARACTER VARYING', 'VARCHAR', 'CHARACTER', 'CHAR'] and \
                field_info['size'] < new_field.size:
                line = 'ALTER TABLE "%s" ALTER COLUMN "%s" TYPE %s(%d) ' % \
                    (table_name, new_field.field_name, field_info['data_type'], new_field.size)
                result.append(line)
        if old_field.default_value != new_field.default_value:
            if not default_text is None:
                line = 'ALTER TABLE "%s" ALTER "%s" SET DEFAULT %s' % \
                    (table_name, new_field.field_name, default_text)
            else:
                line = 'ALTER TABLE "%s" ALTER "%s" DROP DEFAULT' % \
                    (table_name, new_field.field_name)
            result.append(line)
        return result

    def create_index(self, index_name, table_name, unique, fields, desc):
        return 'CREATE %s INDEX "%s" ON "%s" (%s)' % (unique, index_name, table_name, fields)

    def drop_index(self, table_name, index_name):
        return 'DROP INDEX "%s"' % index_name

    def create_foreign_index(self, table_name, index_name, key, ref, primary_key):
        return 'ALTER TABLE "%s" ADD CONSTRAINT "%s" FOREIGN KEY ("%s") REFERENCES "%s"("%s") MATCH SIMPLE' % \
            (table_name, index_name, key, ref, primary_key)

    def drop_foreign_index(self, table_name, index_name):
        return 'ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table_name, index_name)

    def insert_query(self, pk_field):
        return 'INSERT INTO %s (%s) VALUES (%s)'



    def before_insert(self, cursor, pk_field):
        """
        Auto-increment integer primary key for Databricks.
        Only executes if PK exists and is currently None.
        """
        if not pk_field or pk_field.data is not None:
            # PK either doesn't exist or is already set — do nothing
            return

        # Get the table name from the pk_field owner
        table_name = pk_field.owner.table_name
        if not table_name:
            raise ValueError("Cannot determine table name for PK auto-increment")

        # Get catalog and schema from Jam.py task_db_info
        db_name = self.app.admin.task_db_info.database
        catalog, schema = self.parse_database(db_name)

        # Fully qualified table name
        table_sql = f'`{catalog}`.`{schema}`.`{table_name.lower()}`'

        # Debug logging
        import logging
        logging.getLogger().info("Next PK for table: %s, field: %s", table_sql, pk_field.db_field_name)
        import os
        print(f"Table SQL: {table_sql}", file=sys.stderr)


        # Get next PK value
        cursor.execute(f'SELECT COALESCE(MAX(`{pk_field.db_field_name.lower()}`), 0) + 1 FROM {table_sql}')
        pk_field.data = cursor.fetchone()[0]




    def after_insert(self, cursor, pk_field):
        if pk_field and not pk_field.owner.gen_name and not pk_field.data:
            pk_field.data = cursor.fetchone()[0]

    def next_sequence(self, gen_name):
        return 'SELECT NEXTVAL(\'"%s"\')' % gen_name

    def restart_sequence(self, gen_name, value):
        return 'ALTER SEQUENCE "%s" RESTART WITH %d' % (gen_name, value)

    def identifier_case(self, name):
        return name.lower()

    def get_table_names(self, connection):
#        db_name = connection.db_info.database 
        cursor = connection.cursor()

        catalog, schema = self.parse_database(connection.db_info.database)

        if not catalog:
            cursor.execute("SELECT current_catalog()")
            catalog = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT table_name
            FROM `{catalog}`.information_schema.tables
            WHERE table_schema = '{schema}'
        """)
        result = cursor.fetchall()
        return [r[0] for r in result]

#    def parse_database(self, db_name):
#        parts = db_name.split('.')
#        if len(parts) == 2:
#            return parts[0], parts[1]     # catalog, schema
#        elif len(parts) == 1:
#            return None, parts[0]         # schema only
#        else:
#            raise ValueError("Invalid database format")
#
    def parse_database(self, db_name):
        """
        Accepts:
          schema
          catalog.schema
        Returns:
          catalog, schema
        """
        if not db_name:
            return None, None

        parts = db_name.split('.')
        if len(parts) == 2:
            return parts[0].lower(), parts[1].lower()
        elif len(parts) == 1:
            return None, parts[0].lower()
        else:
            raise ValueError(f"Invalid database format: {db_name}")

    def get_table_info(self, connection, table_name, db_name=None):
        cursor = connection.cursor()

        # db_name can be "bakehouse" or "samples.bakehouse"
        catalog, schema = self.parse_database(db_name or connection.db_info.database)

        # if catalog is None, fallback to current catalog
        if not catalog:
            cursor.execute("SELECT current_catalog()")
            catalog = cursor.fetchone()[0]

        sql = f"""
            SELECT column_name, data_type, character_maximum_length, column_default
            FROM `{catalog}`.information_schema.columns
            WHERE table_schema = '{schema}'
              AND table_name = '{table_name}'
        """
        cursor.execute(sql)
        result = cursor.fetchall()

        fields = []

        for column_name, data_type, character_maximum_length, column_default in result:
            # Make field_name lowercase
            field_name_lower = column_name.lower()

            # Default size logic for text types
            if data_type.upper() in ('CHAR', 'VARCHAR', 'STRING', 'TEXT'):
                size = character_maximum_length or 100
            else:
                size = character_maximum_length or 0

            # Default value parsing
            default_value = None
            if column_default:
                default_value = column_default.split('::')[0]
                if 'nextval' in default_value:
                    default_value = None

            fields.append({
                'field_name': field_name_lower,   # use lowercase here
                'data_type': data_type.upper(),
                'size': size,
                'default_value': default_value,
                'pk': False
            })
        return {'fields': fields, 'field_types': self.FIELD_TYPES}

    def update_record(self, delta, cursor):
        self.check_record_version(delta, cursor)
        row = []
        fields = []
        index = 0
        pk = delta._primary_key_field

        if self.db_type == consts.DATABRICKS:
            db_name = self.app.admin.task_db_info.database
            catalog, schema = self.parse_database(db_name)
            table_name_sql = f'`{catalog}`.`{schema}`.`{delta.table_name.lower()}`'
        else:
            table_name_sql = f'"{delta.table_name}"'

        command = f'UPDATE {table_name_sql} SET '

        for field in delta.fields:
            prohibited, read_only = field.restrictions
            if self.db_field(field) and field != pk and not read_only:
                index += 1
                col = f'`{field.db_field_name.lower()}`' if self.db_type == consts.DATABRICKS else f'"{field.db_field_name}"'
                fields.append(f'{col}={self.value_literal(index)}')

                if field.field_name == delta._record_version:
                    field.value += 1
                value = (field.data, field.data_type)
                if field.field_name == delta._deleted_flag:
                    value = (0, field.data_type)
                row.append(value)

        fields_sql = ', '.join(fields)

        # Primary key in WHERE clause
        if delta._primary_key_field.data_type == consts.TEXT:
            id_literal = f"'{delta._primary_key_field.value}'"
        else:
            id_literal = f"{delta._primary_key_field.value}"

        pk_col = f'`{delta._primary_key_db_field_name.lower()}`' if self.db_type == consts.DATABRICKS else f'"{delta._primary_key_db_field_name}"'

        where = f' WHERE {pk_col} = {id_literal}'

        sql = ''.join([command, fields_sql, where])
        row = self.process_query_params(row, cursor)
        delta.execute_query(cursor, sql, row, arg_params=self.arg_params)

    def delete_record(self, delta, cursor):
        """
        Delete a record (soft or hard) from the database.
        Works for Databricks (with catalog.schema.table and backticks)
        and other databases (with double quotes).
        """
        soft_delete = delta.soft_delete
        if delta.master:
            soft_delete = delta.owner.soft_delete

        # Primary key literal
        if delta._primary_key_field.data_type == consts.TEXT:
            id_literal = f"'{delta._primary_key_field.value}'"
        else:
            id_literal = f"{delta._primary_key_field.value}"

        # Databricks: build catalog.schema.table + backticks
        if self.db_type == consts.DATABRICKS:
            db_name = self.app.admin.task_db_info.database
            catalog, schema = self.parse_database(db_name)
            table_name_sql = f'`{catalog}`.`{schema}`.`{delta.table_name.lower()}`'
            pk_col = f'`{delta._primary_key_db_field_name.lower()}`'
            deleted_col = f'`{delta._deleted_flag_db_field_name.lower()}`' if delta._deleted_flag_db_field_name else None
        else:
            # Other databases: default quoting
            table_name_sql = f'"{delta.table_name}"'
            pk_col = f'"{delta._primary_key_db_field_name}"'
            deleted_col = f'"{delta._deleted_flag_db_field_name}"' if delta._deleted_flag_db_field_name else None

        if soft_delete and deleted_col:
            # Soft delete
            sql = f'UPDATE {table_name_sql} SET {deleted_col} = 1 WHERE {pk_col} = {id_literal}'
        else:
            # Hard delete
            sql = f'DELETE FROM {table_name_sql} WHERE {pk_col} = {id_literal}'

        delta.execute_query(cursor, sql)

    def insert_record(self, delta, cursor):
        """
        Insert a new record into the database.
        Works for Databricks (catalog.schema.table, backticks, lowercase columns)
        and other databases (default quoting).
        """
        # Soft-delete flag reset if needed
        if delta._deleted_flag:
            delta._deleted_flag_field.data = 0

        # Primary key
        pk = delta._primary_key_field
        self.before_insert(cursor, pk)  # Auto-increment PK if needed

        row = []
        fields = []
        values = []
        index = 0

        # Prepare fields and values
        for field in delta.fields:
            if not self.db_field(field):
                continue
            if field == pk and not pk.data:
                continue  # PK will be set by before_insert

            index += 1

            # Field quoting
            if self.db_type == consts.DATABRICKS:
                field_name_sql = f'`{field.db_field_name.lower()}`'
            else:
                field_name_sql = f'"{field.db_field_name}"'

            fields.append(field_name_sql)
            values.append(self.value_literal(index))

            # Default value handling
            if field.data is None and field.default_value is not None:
                field.data = field.get_default_value()

            # Add value/type tuple
            value = (field.data, field.data_type)
            if field.field_name == delta._deleted_flag:
                value = (0, field.data_type)
            row.append(value)

        fields_clause = ', '.join(fields)
        values_clause = ', '.join(values)

        # Table quoting
        if self.db_type == consts.DATABRICKS:
            db_name = self.app.admin.task_db_info.database
            catalog, schema = self.parse_database(db_name)
            table_name_sql = f'`{catalog}`.`{schema}`.`{delta.table_name.lower()}`'
        else:
            table_name_sql = f'"{delta.table_name}"'

        # Build SQL
        sql = f'INSERT INTO {table_name_sql} ({fields_clause}) VALUES ({values_clause})'

        # Process params and execute
        row = self.process_query_params(row, cursor)
        delta.execute_query(cursor, sql, row, arg_params=self.arg_params)

        # After-insert hook
        if pk:
            self.after_insert(cursor, pk)


db = DatabricksDB()
