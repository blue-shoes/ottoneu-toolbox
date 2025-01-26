import tkinter as tk     
from tkinter import W
from tkinter import ttk 
from tkinter import messagebox as mb
from ui.dialog.wizard import league_import
from ui.table.table import Table
import logging

from ui.dialog import progress
from services import league_services
from domain.domain import League

class Dialog(tk.Toplevel):
    def __init__(self, parent, active=True):
        super().__init__(parent)
        self.parent = parent
        self.league = None
        self.title("Select a League")
        frm = tk.Frame(self, borderwidth=4)

        self.league_list = league_services.get_leagues(active)

        cols = ('Lg Id', 'Name', 'Platform', 'Format', '# Teams')
        align = {}
        align['Name'] = W
        width = {}
        width['Name'] = 175
        width['Platform'] = 85

        self.league_table = lt = Table(frm, cols, align, width, cols, reverse_col_sort=['Lg Id'])
        lt.grid(row=0, columnspan=4)
        lt.set_row_select_method(self.on_select)
        lt.set_refresh_method(self.populate_table)
        lt.set_double_click_method(self.double_click)
        lt.set_right_click_method(self.rclick)

        self.populate_table()

        ttk.Button(frm, text="OK", command=self.set_league).grid(row=1, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=1, column=1)
        ttk.Button(frm, text="Import New...", command=self.import_league).grid(row=1,column=2)
        ttk.Button(frm, text="Non-Ottoneu", command=self.non_ottoneu).grid(row=1,column=3)

        frm.pack()

        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_window()
    
    def import_league(self):
        try:
            dialog = league_import.Dialog(self.master)
            if dialog.league is not None:
                self.league = dialog.league
                self.destroy()
            else:
                self.lift()
                self.focus_force()
        except Exception:
            mb.showerror('Error downloading league, please try again')
            logging.exception('Error downloading league')
    
    def populate_table(self):
        for lg in self.league_list:
            lgfmt = lg.s_format.short_name
            self.league_table.insert('', tk.END, text=str(lg.id), values=(lg.site_id, lg.name, lg.platform.value, lgfmt, lg.num_teams))

    def double_click(self, event):
        self.on_select(event)
        self.set_league()

    def on_select(self, event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])["text"]
            for lg in self.league_list:
                if lg.id == int(selection):
                    self.league = league_services.get_league(lg.id, rosters=False)
                    break
        else:
            selection = None

    def rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        lg_id = int(event.widget.item(event.widget.selection()[0])["text"])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Delete", command=lambda: self.delete_league(lg_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def delete_league(self, lg_id):
        for lg in self.league_list:
            if lg.id == lg_id:
                league = lg
                break
        if mb.askokcancel('Delete League', f'Confirm deletion of league {league.name}'):
            self.lift()
            pd = progress.ProgressDialog(self.parent, 'Deleting League')
            pd.set_completion_percent(15)
            league_services.delete_league_by_id(lg_id)
            for idx, lg in enumerate(self.league_list):
                if lg.id == lg_id:
                    self.league_list.pop(idx)
                    break
            self.league_table.refresh()
            pd.complete()

    def cancel(self):
        self.league = None
        self.destroy()
    
    def set_league(self):
        self.league = league_services.get_league(self.league.id, rosters=True)
        self.destroy()
    
    def non_ottoneu(self):
        self.league = League()
        self.league.name = 'Non-Ottoneu League'
        self.league.site_id = -1
        self.destroy()