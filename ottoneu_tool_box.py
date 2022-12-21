from ui import main
import sys, getopt

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
    app = main.Main(debug = debug, demo_source=demo_source)
    try:
        app.mainloop()
    except Exception:
        if app.run_event.is_set:
            app.run_event.clear()
    finally:
        if app.run_event.is_set:
            app.run_event.clear()
    