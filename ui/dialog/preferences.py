import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
import os
from tkinter import messagebox as mb
from tkinter.messagebox import OK
import logging

from domain.enum import Preference as Pref, AvgSalaryFom, Browser
from services import salary_services, browser_services
from ui.dialog import progress, fg_login
from util import string_util

class Dialog(tk.Toplevel):
    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.title("Preferences")
        frm = tk.Frame(self, borderwidth=4)

        frm.pack(fill='both', expand=True)

        self.pref = controller.preferences

        validation = frm.register(string_util.int_validation)

        #--General Preferences--
        gen_frame = tk.Frame(frm, pady=5)
        gen_frame.grid(row=0, column=0)
        tk.Label(gen_frame, text='General', font='bold').grid(column=0, row=0, columnspan=2)

        tk.Label(gen_frame, text='Player Universe Refresh Interval (days):').grid(column=0, row=1)
        self.sal_ref_days_tv = StringVar()
        self.sal_ref_days_tv.set(self.pref.getint('General', Pref.SALARY_REFRESH_FREQUENCY, fallback='30'))
        sal_ref_entry = tk.Entry(gen_frame, textvariable=self.sal_ref_days_tv)
        sal_ref_entry.config(validate="key", validatecommand=(validation, '%P'))
        sal_ref_entry.grid(column=1, row=1)

        tk.Button(gen_frame, text='Refresh Now', command=self.refresh_player_universe).grid(column=2, row=1)

        tk.Label(gen_frame, text='Average Salary to Display:').grid(column=0, row=2)
        self.avg_type = StringVar()
        self.avg_type.set(self.pref.get('General', Pref.AVG_SALARY_FOM, fallback=AvgSalaryFom.MEAN))
        avg_type_combo = ttk.Combobox(gen_frame, textvariable=self.avg_type)
        avg_type_combo['values'] = (AvgSalaryFom.MEAN.value, AvgSalaryFom.MEDIAN.value)
        avg_type_combo.grid(column=1, row=2)
        
        #--Value Preferences--
        value_frame = tk.Frame(frm, pady=5)
        value_frame.grid(row=1, column=0)
        tk.Label(value_frame, text='Player Values', font='bold').grid(column=0, row=0, columnspan=2)

        tk.Label(value_frame, text='Default Browser:').grid(column=0, row=1)
        self.browser_type = StringVar()
        
        try:
            browser = browser_services.get_desired_browser()
            self.browser_type.set(browser.display)
        except:
            logging.warning('Bad browser attempted to load in preferences')
        
        browser_combo = ttk.Combobox(value_frame, textvariable=self.browser_type)
        browser_combo['values'] = tuple([e.display for e in Browser])
        browser_combo.grid(column=1, row=1)

        self.fg_auth = fg_auth = StringVar()
        if os.path.exists('conf/fangraphs.conf'):
            fg_auth.set('Credentials entered')
        else:
            fg_auth.set('Credentials needed')
        tk.Label(value_frame, textvariable=fg_auth).grid(row=2, column=0)
        tk.Button(value_frame, command=self.show_fg_dialog, text='Update FG Login').grid(row=2, column=1)

        #--Draft Preferences--
        draft_frame = tk.Frame(frm, pady=5)
        draft_frame.grid(row=2, column=0)
        tk.Label(draft_frame, text='Draft Tool', font='bold').grid(column=0, row=0, columnspan=2)

        tk.Label(draft_frame, text='Stack Targets Table with Position Tables').grid(column=0, row=1)
        self.stack_targets_bv = BooleanVar()
        self.stack_targets_bv.set(self.pref.getboolean('Draft', Pref.DOCK_DRAFT_TARGETS, fallback=False))
        tk.Checkbutton(draft_frame, variable=self.stack_targets_bv).grid(column=1, row=1)

        s_stack_lbl = tk.Label(draft_frame, text='Stack Player Search with Position Tables')
        s_stack_lbl.grid(column=0, row=2)
        #s_stack_lbl.configure(state='disable')

        self.stack_search_bv = BooleanVar()
        self.stack_search_bv.set(self.pref.getboolean('Draft', Pref.DOCK_DRAFT_PLAYER_SEARCH, fallback=False))
        s_stack_cb = tk.Checkbutton(draft_frame, variable=self.stack_search_bv)
        s_stack_cb.grid(column=1, row=2)
        #s_stack_cb.configure(state='disable')

        #--Button Frame--
        button_frame = tk.Frame(frm, pady=5)
        button_frame.grid(row=3, column=0)

        tk.Button(button_frame, command=self.apply, text='Apply', width=7).grid(row=0, column=0, padx=5)
        tk.Button(button_frame, command=self.ok, text='OK', width=7).grid(row=0, column=1, padx=5)
        tk.Button(button_frame, command=self.cancel, text='Cancel', width=7).grid(row=0, column=2, padx=5)

    def refresh_player_universe(self):
        pd = progress.ProgressDialog(self, 'Refreshing Player Universe...')
        pd.set_completion_percent(10)
        salary_services.update_salary_info()
        pd.complete()
    
    def show_fg_dialog(self):
        dialog = fg_login.Dialog(self)
        if dialog == OK:
            self.fg_auth.set('Credentials entered')

    def apply(self):
        changed = False
        changed = self.set_and_check_changed('General', Pref.SALARY_REFRESH_FREQUENCY, self.sal_ref_days_tv.get()) or changed
        changed = self.set_and_check_changed('General', Pref.AVG_SALARY_FOM, self.avg_type.get()) or changed
        self.set_and_check_changed('Player_Values', Pref.DEFAULT_BROWSER, Browser.get_enum_from_display(self.browser_type.get()).value)
        changed = self.set_and_check_changed('Draft', Pref.DOCK_DRAFT_TARGETS, self.get_str_for_boolean_var(self.stack_targets_bv)) or changed
        changed = self.set_and_check_changed('Draft', Pref.DOCK_DRAFT_PLAYER_SEARCH, self.get_str_for_boolean_var(self.stack_search_bv)) or changed

        if not os.path.exists('conf'):
            os.mkdir('conf')
        with open('conf/otb.conf', 'w') as fd:
            self.pref.write(fd)

        if changed:
            self.controller.reload_ui()
    
    def set_and_check_changed(self, group, option, str_val: str):
        if not self.pref.has_section(group):
            self.pref.add_section(group)
            self.pref.set(group, option, str_val)
            return True
        if not self.pref.has_option(group, option):
            self.pref.set(group, option, str_val)
            return True
        if str_val == self.pref.get(group, option):
            return False
        self.pref.set(group, option, str_val)
        return True
    
    def ok(self):
        self.apply()
        self.destroy()

    def cancel(self):
        self.destroy()
    
    def get_str_for_boolean_var(self, bv: BooleanVar):
        if bv.get():
            return 'true'
        else:
            return 'false'


