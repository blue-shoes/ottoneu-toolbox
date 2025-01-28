import tkinter as tk
from tkinter import Event
from tkinter import W
from tkinter import ttk
from tkinter import messagebox as mb

from ui.dialog import progress
from ui.dialog.wizard import projection_import
from ui.table.table import Table, bool_to_table

from services import projection_services, calculation_services


class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.projection = None
        self.deleted_proj_ids = []
        self.title('Select a Projection')
        frm = tk.Frame(self, borderwidth=4)

        top_frm = tk.Frame(frm)
        top_frm.grid(row=0, sticky=tk.E)

        tk.Label(top_frm, text='Select projection season: ').grid(row=0, column=0)
        self.season = tk.StringVar()
        season_cb = ttk.Combobox(top_frm, textvariable=self.season)
        seasons = projection_services.get_available_seasons()
        str_seasons = []
        for season in seasons:
            str_seasons.append(str(season))
        season_cb['values'] = str_seasons
        season_cb.grid(row=0, column=1)
        self.season.set(str_seasons[0])
        season_cb.bind('<<ComboboxSelected>>', self.update_season)

        self.proj_list = projection_services.get_projections_for_year(seasons[0], inc_hidden=False)

        cols = ('Name', 'Detail', 'Type', 'Timestamp', 'RoS?', 'DC PT?')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Name'] = 150
        width['Type'] = 70
        width['Detail'] = 250
        width['Timestamp'] = 70

        self.proj_table = pt = Table(frm, cols, align, width, cols)
        pt.grid(row=1)
        pt.set_row_select_method(self.on_select)
        pt.set_refresh_method(self.populate_table)
        pt.set_double_click_method(self.double_click)
        pt.set_right_click_method(self.rclick)

        self.populate_table()

        bot_frm = tk.Frame(frm)
        bot_frm.grid(row=2, sticky=tk.E)

        ttk.Button(bot_frm, text='OK', command=self.set_projection).grid(row=0, column=0)
        ttk.Button(bot_frm, text='Cancel', command=self.cancel).grid(row=0, column=1)
        ttk.Button(bot_frm, text='Import New...', command=self.import_projection).grid(row=0, column=2)

        frm.pack()

        self.protocol('WM_DELETE_WINDOW', self.cancel)

        self.focus_force()

        self.wait_window()

    def import_projection(self):
        dialog = projection_import.Dialog(self.master)
        if dialog.projection is not None:
            self.projection = dialog.projection
            self.destroy()
        else:
            self.lift()
            self.focus_force()

    def update_season(self, event: Event):
        self.proj_list = projection_services.get_projections_for_year(int(self.season.get()))
        self.proj_table.refresh()

    def populate_table(self):
        for proj in self.proj_list:
            self.proj_table.insert('', tk.END, text=str(proj.id), values=(proj.name, proj.detail, proj.type.type_name, proj.timestamp, bool_to_table(proj.ros), bool_to_table(proj.dc_pt)))

    def double_click(self, event):
        self.on_select(event)
        self.set_projection()

    def on_select(self, event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])['text']
            for proj in self.proj_list:
                if proj.id == int(selection):
                    self.projection = projection_services.get_projection(proj_id=proj.id, player_data=False)
                    break
        else:
            self.projection = None

    def rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        proj_id = int(event.widget.item(event.widget.selection()[0])['text'])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label='Delete', command=lambda: self.delete_proj(proj_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def delete_proj(self, proj_id):
        for projection in self.proj_list:
            if projection.id == proj_id:
                proj = projection
                break
        dep_values = calculation_services.get_values_with_projection_id(proj_id)
        if len(dep_values) > 0:
            if mb.askokcancel('Delete Projection', f'Confirm deletion of projection {proj.name}\n\nNote this projection is used by {len(dep_values)} value sets, which will also be deleted.'):
                self.perform_deletion(projection)
            else:
                self.lift()
                self.focus_force()
        elif mb.askokcancel('Delete Projection', f'Confirm deletion of projection {proj.name}'):
            self.perform_deletion(projection)
        else:
            self.lift()
            self.focus_force()

    def perform_deletion(self, projection):
        self.lift()
        pd = progress.ProgressDialog(self.parent, 'Deleting Projection')
        pd.set_completion_percent(15)
        p_id = projection.id
        projection_services.delete_projection_by_id(projection.id)
        for idx, proj in enumerate(self.proj_list):
            if proj.id == p_id:
                self.proj_list.pop(idx)
                break
        self.proj_table.refresh()
        self.deleted_proj_ids.append(p_id)
        pd.complete()

    def cancel(self):
        self.projection = None
        self.destroy()

    def set_projection(self):
        self.destroy()
