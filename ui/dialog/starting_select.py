import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb

from ui.dialog import progress
from ui.dialog.wizard import starting_position
from ui.table.table import Table, bool_to_table
from domain.domain import StartingPositionSet

from services import starting_positions_services

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.starting_set = None
        self.deleted_starting_set_ids = []
        self.title("Select a Starting Position Set")
        frm = tk.Frame(self, borderwidth=4)

        top_frm = tk.Frame(frm)
        top_frm.grid(row=0, sticky=tk.E)

        self.starting_set_list = starting_positions_services.get_all_starting_sets()

        cols = ('Name', 'Detail')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Name'] = 150
        width['Detail'] = 250

        self.starting_set_table = sst = Table(frm, cols, align, width, cols)
        sst.grid(row=0)
        sst.set_row_select_method(self.on_select)
        sst.set_refresh_method(self.populate_table)
        sst.set_double_click_method(self.double_click)
        sst.set_right_click_method(self.rclick)

        self.populate_table()

        bot_frm = tk.Frame(frm)
        bot_frm.grid(row=1, sticky=tk.E)

        ttk.Button(bot_frm, text="OK", command=self.set_starting_set).grid(row=0, column=0)
        ttk.Button(bot_frm, text="Cancel", command=self.cancel).grid(row=0, column=1)
        ttk.Button(bot_frm, text="Create New...", command=self.create_starting_set).grid(row=0,column=2)

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.focus_force()

        self.wait_window()
    
    def create_starting_set(self):
        dialog = starting_position.Dialog(self.master)
        if dialog.starting_set is not None:
            self.starting_set = dialog.starting_set
            self.destroy()
        else:
            self.lift()
            self.focus_force()
    
    def populate_table(self):
        for starting_set in self.starting_set_list:
            self.starting_set_table.insert('', tk.END, text=str(starting_set.id), values=(starting_set.name, starting_set.detail))

    def double_click(self, event):
        self.on_select(event)
        self.set_starting_set()

    def on_select(self, event:Event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])["text"]
            for starting_set in self.starting_set_list:
                if starting_set.id == int(selection):
                    self.starting_set = starting_set
                    break
        else:
            self.starting_set = None
    
    def rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        starting_set_id = int(event.widget.item(event.widget.selection()[0])["text"])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Delete", command=lambda: self.delete_starting_set(starting_set_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def delete_starting_set(self, starting_set_id:int):
        for starting_set in self.starting_set_list:
            if starting_set.id == starting_set_id:
                sf = starting_set
                break
        if mb.askokcancel('Delete Starting Position Set', f'Confirm deletion of starting set {sf.name}'):
            self.perform_deletion(starting_set)
        else:
            self.lift()
            self.focus_force()

    def perform_deletion(self, starting_set:StartingPositionSet):
        self.lift()
        pd = progress.ProgressDialog(self.parent, 'Deleting Starting Position Set')
        pd.set_completion_percent(15)
        starting_positions_services.delete_by_id(starting_set.id)
        self.starting_set_list.remove(starting_set)
        self.starting_set_table.refresh()
        self.deleted_starting_set_ids.append(starting_set.id)
        pd.complete()

    def cancel(self):
        self.starting_set = None
        self.destroy()
    
    def set_starting_set(self):
        self.destroy()