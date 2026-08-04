
from ..common import consts

def get_database(app, db_type, lib):
    db = None
    if db_type == consts.SQLITE:
        from .sqlite_db import db
    elif db_type == consts.POSTGRESQL:
        from .postgres_db import db
    elif db_type == consts.MYSQL:
        if lib == 1:
            from .mysql_db1 import db
        elif lib == 2:
            from .mysql_db2 import db
        else:
            from .mysql_db import db
    elif db_type == consts.FIREBIRD:
        from .firebird_db import db
        if lib == 1:
            from .firebird_db1 import db
        elif lib == 2:
            from .firebird_db2 import db
        elif lib == 3:
            from .firebird_db3 import db
        else:
            from .firebird_db import db
    elif db_type == consts.ORACLE:
        from .oracle_db import db
        if lib == 1:
            from .oracle_db1 import db
        elif lib == 2:
            from .oracle_db2 import db
        else:
            from .oracle_db import db
    elif db_type == consts.MSSQL:
        if lib == 1:
            from .mssql_db1 import db
        elif lib == 2:
            from .mssql_db2 import db
        else:
            from .mssql_db import db
    elif db_type == consts.DUCKDB:
        from .duck_db import db
        if lib == 1:
            from .duck_db1 import db
        elif lib == 2:
            from .duck_db2 import db
        else:
            from .duck_db import db
    elif db_type == consts.DATABRICKS:
        from .databricks_db import db
    if db:
        db.app = app
    return db
