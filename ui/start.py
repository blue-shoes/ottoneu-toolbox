import tkinter as tk
from tkinter import ttk

from ui.app_controller import Controller
from ui.toolbox_view import ToolboxView


class Start(ToolboxView):
    def __init__(self, parent: tk.Frame, controller: Controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        main_lbl = ttk.Label(self, text='Select a module', font='bold')
        main_lbl.grid(column=0, row=0, pady=5, columnspan=2)

        ttk.Button(self, text='Create Player Values', command=self.create_player_values_click).grid(column=0, row=1)
        ttk.Button(self, text='Run Draft Tracker', command=self.run_draft_tracker).grid(column=1, row=1)
        ttk.Button(self, text='League Analysis', command=self.open_league_analysis).grid(column=0, row=2)
        ttk.Button(self, text='Exit', command=self.exit).grid(column=1, row=2)

        self.pack()

    def on_show(self):
        return True

    def leave_page(self):
        return True

    def league_change(self) -> bool:
        return True

    def value_change(self) -> bool:
        return True

    def create_player_values_click(self):
        self.controller.show_player_values()

    def run_draft_tracker(self):
        self.controller.show_draft_tracker()

    def open_league_analysis(self):
        self.controller.show_league_analysis()

    def exit(self):
        self.controller.exit()
