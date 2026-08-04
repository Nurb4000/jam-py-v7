#import firebird-driver
from firebird.driver import connect

from .firebird_db import FirebirdDB

class FirebirdDB1(FirebirdDB):
    def __init__(self):
        FirebirdDB.__init__(self)

    def connect(self, db_info):
        if not db_info.database:
            raise Exception('Must supply database')
        else:
            if db_info.host:
                database = f"{db_info.host}:{db_info.database}"

            return connect(database,
                user=db_info.user,
                password=db_info.password,
                charset=db_info.encoding,)

db = FirebirdDB1()
