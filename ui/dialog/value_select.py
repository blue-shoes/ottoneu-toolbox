import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
#from ui.dialog import value_import
from ui.table import Table, bool_to_table
from domain.enum import CalculationDataType
from tkinter import messagebox as mb

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

        self.populate_table()

        ttk.Button(frm, text="OK", command=self.set_value).grid(row=1, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=1, column=1)
        ttk.Button(frm, text="Import From File...", command=self.import_values).grid(row=1,column=2)
        if redirect:
            ttk.Button(frm, text="Create New Values...", command=self.open_create_values).grid(row=1,column=3)

        frm.pack()

        self.wait_window()
    
    def import_values(self):
        #dialog = value_import.Dialog(self.master)
        #if dialog.value is not None:
        #    self.value = dialog.value
        #    self.destroy()
        mb.showwarning("Import values not currently supported")
    
    def open_create_values(self):
        self.page_controller.show_player_values()
        self.destroy()
    
    def populate_table(self):
        for value in self.value_list:
            self.value_table.insert('', tk.END, text=str(value.index), values=(value.name, ScoringFormat.enum_to_short_name_map()[value.format], int(value.get_input(CalculationDataType.NUM_TEAMS)), value.description))
        self.value_table.treeview_sort_column(self.value_table.sort_col, self.value_table.reverse_sort)

    def on_select(self, event):
        selection = event.widget.item(event.widget.selection()[0])["text"]
        for value in self.value_list:
            if value.index == int(selection):
                self.value = calculation_services.load_calculation(value.index)
                break

    def cancel(self):
        self.value = None
        self.destroy()
    
    def set_value(self):
        self.destroy()