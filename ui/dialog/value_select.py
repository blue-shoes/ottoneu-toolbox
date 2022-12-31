import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from ui.dialog.wizard import value_import
from ui.table import Table
from ui.dialog import progress
from domain.enum import CalculationDataType, ScoringFormat

from services import calculation_services

class Dialog(tk.Toplevel):
    def __init__(self, parent, page_controller, active=True, year=None, redirect=True):
        super().__init__(parent)
        self.value = None
        self.title("Select a Value Set")
        self.page_controller = page_controller
        frm = tk.Frame(self, borderwidth=4)

        self.value_list = calculation_services.get_values_for_year(year=year)

        cols = ('Name', 'Format', '# Teams', 'Details')
        align = {}
        align['Name'] = W
        align['Details'] = W
        width = {}
        width['Name'] = 175
        width['Details'] = 300

        self.value_table = lt = Table(frm, cols, align, width, cols)
        span = 3
        if redirect:
            span = 4
        lt.grid(row=0, columnspan=span)
        lt.set_row_select_method(self.on_select)
        lt.set_refresh_method(self.populate_table)
        lt.set_double_click_method(self.double_click)

        self.populate_table()

        ttk.Button(frm, text="OK", command=self.set_value).grid(row=1, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=1, column=1)
        ttk.Button(frm, text="Import From File...", command=self.import_values).grid(row=1,column=2)
        if redirect:
            ttk.Button(frm, text="Create New Values...", command=self.open_create_values).grid(row=1,column=3)

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.focus_force()

        self.wait_window()
    
    def import_values(self):
        dialog = value_import.Dialog(self.master)
        if dialog.value is not None:
            self.value = dialog.value
            self.destroy()
    
    def open_create_values(self):
        self.page_controller.show_player_values()
        self.destroy()
    
    def populate_table(self):
        for value in self.value_list:
            self.value_table.insert('', tk.END, text=str(value.index), values=(value.name, ScoringFormat.enum_to_short_name_map()[value.format], int(value.get_input(CalculationDataType.NUM_TEAMS)), value.description))

    def double_click(self, event):
        self.on_select(event)
        self.set_value()

    def on_select(self, event):
        selection = event.widget.item(event.widget.selection()[0])["text"]
        for value in self.value_list:
            if value.index == int(selection):
                self.value = value
                break

    def cancel(self):
        self.value = None
        self.destroy()
    
    def set_value(self):
        pd = progress.ProgressDialog(self.master, title='Loading Values...')
        pd.set_completion_percent(15)
        self.value = calculation_services.load_calculation(self.value.index)
        pd.set_completion_percent(100)
        pd.destroy()
        self.destroy()