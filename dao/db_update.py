import sqlite3
import os
import logging
from sqlite3 import OperationalError

def run_db_updates(sql_files):
    conn = sqlite3.connect(os.path.join('db', 'otto_toolbox.db'))
    c = conn.cursor()

    for file in sql_files:
        logging.info(f'Running script {file}')
        with open(file, 'r') as fd:
            sqlFile = fd.read()
        sqlCommands = sqlFile.split(';')

        for command in sqlCommands:
            try:
                c.execute(command)
            except OperationalError as Argument:
                logging.exception(f'Error running sql command {command}')
    c.close()
    conn.close()