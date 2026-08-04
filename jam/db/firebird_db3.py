import firebirdsql

from .firebird_db import FirebirdDB

class FirebirdDB3(FirebirdDB):
    def __init__(self):
        FirebirdDB.__init__(self)

    def connect(self, db_info):
        if not db_info.database:
            raise Exception('Must supply database')
        else:
            return firebirdsql.connect(database=db_info.database, user=db_info.user,
                password=db_info.password, charset=db_info.encoding,
                host=db_info.host, port=db_info.port)

db = FirebirdDB3()
