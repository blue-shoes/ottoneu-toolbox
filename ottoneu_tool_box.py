from ui import main
import sys, getopt, os

def resource_path(end_file):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'resources', end_file)

if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        opts, args = getopt.getopt(args, 'ds')
    except getopt.GetoptError:
        print('Opt error, exiting')
        exit(1)
    debug = False
    demo_source = False
    for opt, arg in opts:
        if opt == '-d':
            debug = True
        if opt == '-s':
            demo_source = True
    app = main.Main(debug = debug, demo_source=demo_source, resource_path=resource_path)
    try:
        app.mainloop()
    except Exception:
        if app.run_event.is_set:
            app.run_event.clear()
    finally:
        if app.run_event.is_set:
            app.run_event.clear()
    