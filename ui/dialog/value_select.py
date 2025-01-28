import tkinter as tk
from tkinter import Event
from tkinter import W
from tkinter import ttk
from tkinter import messagebox as mb

from ui.dialog.wizard import value_import
from ui.table.table import Table
from ui.dialog import progress
from domain.enum import CalculationDataType, ScoringFormat

from services import calculation_services, custom_scoring_services


class Dialog(tk.Toplevel):
    def __init__(self, parent, page_controller, active=True, year=None, redirect=True):
        super().__init__(parent)
        self.parent = parent
        self.value = None
        self.title('Select a Value Set')
        self.page_controller = page_controller
        frm = tk.Frame(self, borderwidth=4)

        tk.Label(frm, text='Select value set season: ').grid(row=0, column=0)
        self.season = tk.StringVar()
        season_cb = ttk.Combobox(frm, textvariable=self.season)
        seasons = calculation_services.get_available_seasons()
        str_seasons = []
        for season in seasons:
            str_seasons.append(str(season))
        season_cb['values'] = str_seasons
        season_cb.grid(row=0, column=1)
        self.season.set(str_seasons[0])
        season_cb.bind('<<ComboboxSelected>>', self.update_season)

        self.value_list = calculation_services.get_values_for_year(year=seasons[0])

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
        lt.grid(row=1, columnspan=span)
        lt.set_row_select_method(self.on_select)
        lt.set_refresh_method(self.populate_table)
        lt.set_double_click_method(self.double_click)
        lt.set_right_click_method(self.rclick)

        self.populate_table()

        ttk.Button(frm, text='OK', command=self.set_value).grid(row=2, column=0)
        ttk.Button(frm, text='Cancel', command=self.cancel).grid(row=2, column=1)
        ttk.Button(frm, text='Import From File...', command=self.import_values).grid(row=2, column=2)
        if redirect:
            ttk.Button(frm, text='Create New Values...', command=self.open_create_values).grid(row=2, column=3)

        frm.pack()

        self.protocol('WM_DELETE_WINDOW', self.cancel)

        self.focus_force()

        self.wait_window()

    def import_values(self):
        dialog = value_import.Dialog(self.master)
        if dialog.value is not None:
            self.value = dialog.value
            self.destroy()
        else:
            self.lift()
            self.focus_force()

    def open_create_values(self):
        self.page_controller.show_player_values()
        self.destroy()

    def update_season(self, event: Event):
        self.value_list = calculation_services.get_values_for_year(int(self.season.get()))
        self.value_table.refresh()

    def populate_table(self):
        for value in self.value_list:
            if value.s_format == ScoringFormat.CUSTOM:
                v_type = custom_scoring_services.get_scoring_format(value.get_input(CalculationDataType.CUSTOM_SCORING_FORMAT)).name
            else:
                v_type = value.s_format.short_name
            self.value_table.insert('', tk.END, text=str(value.id), values=(value.name, v_type, int(value.get_input(CalculationDataType.NUM_TEAMS)), value.description))

    def double_click(self, event):
        self.on_select(event)
        self.set_value()

    def on_select(self, event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])['text']
            for value in self.value_list:
                if value.id == int(selection):
                    self.value = value
                    break
        else:
            self.value = None

    def rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        value_id = int(event.widget.item(event.widget.selection()[0])['text'])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label='Delete', command=lambda: self.delete_values(value_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def delete_values(self, values_id):
        for values in self.value_list:
            if values.id == values_id:
                val = values
                break
        if mb.askokcancel('Delete Values', f'Confirm deletion of values {val.name}'):
            self.lift()
            pd = progress.ProgressDialog(self.parent, 'Deleting Values')
            pd.set_completion_percent(15)
            calculation_services.delete_values_by_id(values_id)
            for idx, vc in enumerate(self.value_list):
                if vc.id == values_id:
                    self.value_list.pop(idx)
                    break
            self.value_table.refresh()
            pd.complete()

    def cancel(self):
        self.value = None
        self.destroy()

    def set_value(self):
        pd = progress.ProgressDialog(self.master, title='Loading Values...')
        pd.set_completion_percent(15)
        self.value = calculation_services.load_calculation(self.value.id)
        pd.set_completion_percent(100)
        pd.destroy()
        self.destroy()
