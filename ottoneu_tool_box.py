from ui.main import Main
#import icecream
#from icecream.icecream import ic
import sys
import getopt
import os
import shutil

import logging

def resource_path(end_file) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'resources', end_file)

def main():
    #icecream.install() #Install icecream debugger for use in rest of program
    args = sys.argv[1:]
    try:
        opts, args = getopt.getopt(args, 'dsb:')
    except getopt.GetoptError:
        print('Opt error, exiting')
        exit(1)
    debug = False
    demo_source = False
    bkup = False
    bkup_db = None
    for opt, arg in opts:
        if opt == '-d':
            debug = True
        if opt == '-s':
            demo_source = True
        if opt == '-b':
            bkup = True
            db_dir = 'db'
            if not os.path.exists(db_dir):
                os.mkdir(db_dir)
            bkup_path = os.path.join('db','bkup')
            if not os.path.exists(bkup_path):
                os.mkdir(bkup_path)
            db_loc = os.path.join('db', 'otto_toolbox.db')
            if os.path.exists(db_loc):
                bkup_db = os.path.join(bkup_path, 'otto_toolbox.db')
                shutil.move(db_loc, bkup_db)
            shutil.copy(arg, db_loc)
    app = Main(debug = debug, demo_source=demo_source, resource_path=resource_path)
    try:
        app.mainloop()
    except Exception:
        if not app.run_event.is_set():
            app.run_event.set()
        logging.exception('Fatal Application Exception')
    finally:
        if not app.run_event.is_set():
            app.run_event.set()
        if bkup:
            os.remove(db_loc)
            if bkup_db is not None:
                shutil.move(bkup_db, db_loc)

if __name__ == "__main__":
    main()