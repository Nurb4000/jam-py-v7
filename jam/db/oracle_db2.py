import cx_Oracle

from ..common import consts
from .db import AbstractDB

class OracleDB2(AbstractDB):
    def __init__(self):
        OracleDB.__init__(self)

    def connect(self, db_info):
        if db_info.dsn:
            return cx_Oracle.connect(user=db_info.user, password=db_info.password, dsn=db_info.database)
        else:
            return cx_Oracle.connect(dsn=db_info.dsn)            

db = OracleDB2()
