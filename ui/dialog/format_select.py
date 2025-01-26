import tkinter as tk     
from tkinter import Event
from tkinter import W
from tkinter import ttk 
from tkinter import messagebox as mb

from ui.dialog import progress
from ui.dialog.wizard import custom_scoring
from ui.table.table import Table, bool_to_table
from domain.domain import CustomScoring

from services import custom_scoring_services

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.scoring = None
        self.deleted_format_ids = []
        self.title("Select a Scoring Format")
        frm = tk.Frame(self, borderwidth=4)

        top_frm = tk.Frame(frm)
        top_frm.grid(row=0, sticky=tk.E)

        self.format_list = custom_scoring_services.get_all_formats()

        cols = ('Name', 'Detail', 'Points?')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Name'] = 150
        width['Detail'] = 250
        width['Points'] = 40

        self.format_table = pt = Table(frm, cols, align, width, cols)
        pt.grid(row=0)
        pt.set_row_select_method(self.on_select)
        pt.set_refresh_method(self.populate_table)
        pt.set_double_click_method(self.double_click)
        pt.set_right_click_method(self.rclick)

        self.populate_table()

        bot_frm = tk.Frame(frm)
        bot_frm.grid(row=1, sticky=tk.E)

        ttk.Button(bot_frm, text="OK", command=self.set_format).grid(row=0, column=0)
        ttk.Button(bot_frm, text="Cancel", command=self.cancel).grid(row=0, column=1)
        ttk.Button(bot_frm, text="Create New...", command=self.create_scoring_format).grid(row=0,column=2)

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.focus_force()

        self.wait_window()
    
    def create_scoring_format(self):
        dialog = custom_scoring.Dialog(self.master)
        if dialog.scoring is not None:
            self.scoring = dialog.scoring
            self.destroy()
        else:
            self.lift()
            self.focus_force()
    
    def populate_table(self):
        for scoring_format in self.format_list:
            self.format_table.insert('', tk.END, text=str(scoring_format.id), values=(scoring_format.name, scoring_format.description, bool_to_table(scoring_format.points_format)))

    def double_click(self, event):
        self.on_select(event)
        self.set_format()

    def on_select(self, event:Event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])["text"]
            for scoring_format in self.format_list:
                if scoring_format.id == int(selection):
                    self.scoring = scoring_format
                    break
        else:
            self.scoring = None
    
    def rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        scoring_format_id = int(event.widget.item(event.widget.selection()[0])["text"])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Delete", command=lambda: self.delete_format(scoring_format_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def delete_format(self, format_id:int):
        for scoring_format in self.format_list:
            if scoring_format.id == format_id:
                sf = scoring_format
                break
        if mb.askokcancel('Delete Scoring Format', f'Confirm deletion of scoring format {sf.name}'):
            self.perform_deletion(scoring_format)
        else:
            self.lift()
            self.focus_force()

    def perform_deletion(self, scoring_format:CustomScoring):
        self.lift()
        pd = progress.ProgressDialog(self.parent, 'Deleting Scoring Format')
        pd.set_completion_percent(15)
        custom_scoring_services.delete_by_id(scoring_format.id)
        self.format_list.remove(scoring_format)
        self.format_table.refresh()
        self.deleted_format_ids.append(scoring_format.id)
        pd.complete()

    def cancel(self):
        self.scoring = None
        self.destroy()
    
    def set_format(self):
        self.destroy()