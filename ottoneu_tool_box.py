from ui import main
import sys, getopt

if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        opts, args = getopt.getopt(args, 'd')
    except getopt.GetoptError:
        print('Opt error, exiting')
        exit(1)
    debug = False
    for opt, arg in opts:
        if opt == '-d':
            debug = True
    app = main.Main(debug = debug)
    try:
        app.mainloop()
    except Exception:
        if app.run_event.is_set:
            app.run_event.clear()
    finally:
        if app.run_event.is_set:
            app.run_event.clear()
    