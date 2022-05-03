import sqlite3
import os
from os import path

class Connection(object):
    def __init__(self, db_loc=None):
        if db_loc == None:
            dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
            db_loc = os.path.join(dirname, 'db', 'otto_toolbox.db')
        self.conn = sqlite3.connect(db_loc)