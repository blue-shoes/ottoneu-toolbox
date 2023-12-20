import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb

from ui.dialog import progress
from ui.table.table import Table
from domain.domain import PositionSet

from services import position_set_services

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.pos_set = None
        self.deleted_position_set_ids = []
        self.title("Select a Position Set")
        frm = tk.Frame(self, borderwidth=4)

        top_frm = tk.Frame(frm)
        top_frm.grid(row=0, sticky=tk.E)

        self.position_set_list = position_set_services.get_all_position_sets()

        cols = ('Name', 'Detail')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Name'] = 150
        width['Detail'] = 250

        self.position_set_table = pt = Table(frm, cols, align, width, cols)
        pt.grid(row=0)
        pt.set_row_select_method(self.on_select)
        pt.set_refresh_method(self.populate_table)
        pt.set_double_click_method(self.double_click)
        pt.set_right_click_method(self.rclick)

        self.populate_table()

        bot_frm = tk.Frame(frm)
        bot_frm.grid(row=1, sticky=tk.E)

        ttk.Button(bot_frm, text="OK", command=self.set_position_set).grid(row=0, column=0)
        ttk.Button(bot_frm, text="Cancel", command=self.cancel).grid(row=0, column=1)

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.focus_force()

        self.wait_window()
    
    def populate_table(self):
        self.position_set_table.insert('', tk.END, text=str(-1), values=('Ottoneu', 'Current Ottoneu Eligibility'))
        for position_set in self.position_set_list:
            self.position_set_table.insert('', tk.END, text=str(position_set.id), values=(position_set.name, position_set.detail))

    def double_click(self, event):
        self.on_select(event)
        self.set_position_set()

    def on_select(self, event:Event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])["text"]
            selection_id = int(selection)
            if selection_id == -1:
                self.pos_set = None
            else:
                for position_set in self.position_set_list:
                    if position_set.id == selection_id:
                        self.pos_set = position_set
                        break
        else:
            self.pos_set = None
    
    def rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        position_set_id = int(event.widget.item(event.widget.selection()[0])["text"])
        if position_set_id == -1:
            return
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Delete", command=lambda: self.delete_position_set(position_set_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def delete_position_set(self, position_set_id:int):
        for position_set in self.position_set_list:
            if position_set.id == position_set_id:
                sf = position_set
                break
        if mb.askokcancel('Delete Position Set', f'Confirm deletion of position set {sf.name}. This will also remove it from any Leagues or Value sets.'):
            self.perform_deletion(position_set)
        else:
            self.lift()
            self.focus_force()

    def perform_deletion(self, position_set:PositionSet):
        self.lift()
        pd = progress.ProgressDialog(self.parent, 'Deleting Position Set')
        pd.set_completion_percent(15)
        position_set_services.delete_by_id(position_set.id)
        self.position_set_list.remove(position_set)
        self.position_set_table.refresh()
        self.deleted_position_set_ids.append(position_set.id)
        pd.complete()

    def cancel(self):
        self.pos_set = None
        self.destroy()
    
    def set_position_set(self):
        self.destroy()