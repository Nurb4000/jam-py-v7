import oracledb

from ..common import consts
from .db import AbstractDB

class OracleDB1(OracleDB):
    def __init__(self):
        OracleDB.__init__(self)

    def connect(self, db_info):
        if db_info.dsn:
            return oracledb.connect(dsn=db_info.dsn)
        else:
            return oracledb.connect(user=db_info.user, password=db_info.password, dsn=db_info.database)

db = OracleDB1()
