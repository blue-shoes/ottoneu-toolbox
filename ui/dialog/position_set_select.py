import tkinter as tk
from tkinter import StringVar, Event
from tkinter import W
from tkinter import ttk
from tkinter import messagebox as mb
from tkinter import filedialog as fd
from pathlib import Path
import os
import pandas as pd

from ui.dialog import progress
from ui.table.table import Table
from domain.domain import PositionSet
from domain.enum import IdType

from services import position_set_services


class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.pos_set = None
        self.deleted_position_set_ids = []
        self.title('Select a Position Set')
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

        ttk.Button(bot_frm, text='OK', command=self.set_position_set).grid(row=0, column=0)
        ttk.Button(bot_frm, text='Cancel', command=self.cancel).grid(row=0, column=1)
        ttk.Button(bot_frm, text='Import Set', command=self.import_set).grid(row=0, column=2)

        frm.pack()

        self.protocol('WM_DELETE_WINDOW', self.cancel)

        self.focus_force()

        self.wait_window()

    def populate_table(self):
        for position_set in self.position_set_list:
            self.position_set_table.insert('', tk.END, text=str(position_set.id), values=(position_set.name, position_set.detail))

    def double_click(self, event):
        self.on_select(event)
        self.set_position_set()

    def on_select(self, event: Event):
        if len(event.widget.selection()) > 0:
            selection = event.widget.item(event.widget.selection()[0])['text']
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
        position_set_id = int(event.widget.item(event.widget.selection()[0])['text'])
        if position_set_id == -1:
            return
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label='Export to File', command=lambda: self.export_to_file(position_set_id))
        popup.add_command(label='Delete', command=lambda: self.delete_position_set(position_set_id))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def export_to_file(self, selection_id: int):
        filetypes = (('csv files', '*.csv'), ('All files', '*.*'))

        file = fd.asksaveasfilename(title='Save As...', initialdir=Path.home(), filetypes=filetypes)

        if file is None:
            return

        for position_set in self.position_set_list:
            if position_set.id == selection_id:
                export_set = position_set
                break

        position_set_services.write_position_set_to_csv(export_set, file)

    def delete_position_set(self, position_set_id: int):
        for position_set in self.position_set_list:
            if position_set.id == position_set_id:
                sf = position_set
                break
        if mb.askokcancel('Delete Position Set', f'Confirm deletion of position set {sf.name}. This will also remove it from any Leagues or Value sets.'):
            self.perform_deletion(position_set)
        else:
            self.lift()
            self.focus_force()

    def perform_deletion(self, position_set: PositionSet):
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

    def import_set(self):
        i_dialog = ImportPositionSetDialog(self)
        if i_dialog.pos_set:
            self.pos_set = i_dialog.pos_set
            self.destroy()


class ImportPositionSetDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title('Import a Position Set')
        frm = tk.Frame(self, borderwidth=4)
        frm.grid(columnspan=2)

        tk.Label(frm, text='Name:').grid(row=1, column=0)
        self.name_tv = StringVar()
        tk.Entry(frm, textvariable=self.name_tv).grid(row=1, column=1)

        tk.Label(frm, text='Description:').grid(row=2, column=0)
        self.desc_tv = StringVar()
        tk.Entry(frm, textvariable=self.desc_tv).grid(row=2, column=1)

        file_label = ttk.Label(frm, text='Player Value File (csv):')
        file_label.grid(column=0, row=3, pady=5, stick=W)

        self.position_set_file = tk.StringVar()
        file_btn = ttk.Button(frm, textvariable=self.position_set_file, command=self.select_position_file)
        file_btn.grid(column=1, row=3, padx=5, sticky='we', columnspan=2)
        self.position_set_file.set(Path.home())

        id_map = [IdType.OTTONEU.value, IdType.FANGRAPHS.value, IdType.MLB.value]
        ttk.Label(frm, text='Player Id Type:').grid(column=0, row=4, pady=5, stick=W)
        self.id_type = StringVar()
        self.id_type.set(IdType.OTTONEU.value)
        id_combo = ttk.Combobox(frm, textvariable=self.id_type)
        id_combo['values'] = id_map
        id_combo.grid(column=1, row=4, pady=5, columnspan=2)

        ttk.Button(self, text='OK', command=self.set_position_set).grid(row=1, column=0)
        ttk.Button(self, text='Cancel', command=self.cancel).grid(row=1, column=1)

        # frm.pack()

        self.protocol('WM_DELETE_WINDOW', self.cancel)

        self.focus_force()

        self.wait_window()

    def select_position_file(self):
        filetypes = (('csv files', '*.csv'), ('All files', '*.*'))

        title = 'Choose a position set file'
        if os.path.isfile(self.position_set_file.get()):
            init_dir = os.path.dirname(self.position_set_file.get())
        else:
            init_dir = self.position_set_file.get()

        while True:
            file = fd.askopenfilename(title=title, initialdir=init_dir, filetypes=filetypes)

            if not file:
                return

            test_df = pd.read_csv(file, encoding='utf-8')
            col_map = dict([(col, col.upper()) for col in test_df.columns])
            test_df.rename(col_map, inplace=True)
            if set(['ID', 'NAME', 'TEAM', 'POS']).issubset(test_df.columns):
                break
            mb.showwarning('Insufficient data', 'The position file must have the following columns: ID, NAME, TEAM, POS')

        self.position_set_file.set(file)

        self.parent.parent.lift()
        self.parent.parent.focus_force()

    def cancel(self):
        self.pos_set = None
        self.destroy()

    def set_position_set(self):
        df = pd.read_csv(self.position_set_file.get(), encoding='utf-8')
        col_map = dict([(col, col.upper()) for col in df.columns])
        df.rename(col_map, inplace=True)
        self.pos_set = position_set_services.create_position_set_from_df(df, IdType._value2member_map_.get(self.id_type.get(), None), self.name_tv.get(), self.desc_tv.get())
        self.destroy()
