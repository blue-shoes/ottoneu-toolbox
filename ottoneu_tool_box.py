from ui import main

if __name__ == "__main__":
    app = main.Main()
    try:
        app.mainloop()
    except Exception:
        if app.run_event.is_set:
            app.run_event.clear()
    finally:
        if app.run_event.is_set:
            app.run_event.clear()
    