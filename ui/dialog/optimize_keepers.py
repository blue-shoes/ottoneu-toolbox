import tkinter as tk
from tkinter import *    
from tkinter import messagebox as mb

class Dialog(tk.Toplevel):
    def __init__(self, parent, inflation:float):
        super().__init__(parent)
        self.title("Optimize keepers")
        self.frm = frm = tk.Frame(self, borderwidth=4)

        self.current_inflation = inflation * 100

        frm.pack(fill='both', expand=True)

        tk.Label(frm, text='Set Target Inflation', font='bold').grid(row=0, column=0, columnspan=2)

        self.inflation_sv = StringVar()
        self.inflation_sv.set('0.0')

        self.target_type = IntVar()
        self.target_type.set(0)

        tk.Radiobutton(frm, text='Surplus Only', variable=self.target_type, value=0, anchor='w', command=self.update_type).grid(row=1, column=0, columnspan=2)
        tk.Radiobutton(frm, text='Up to Target Inflation', variable=self.target_type, value=1, anchor='w', command=self.update_type).grid(row=2, column=0, columnspan=2)
        
        self.ti_lbl = tk.Label(frm, text='Target Inflation (%)')
        self.ti_lbl.grid(row=3, column=0)
        self.ti_entry = tk.Entry(frm, textvariable=self.inflation_sv)
        self.ti_entry.grid(row=3, column=1)

        self.ti_lbl['state'] = DISABLED
        self.ti_entry['state'] = DISABLED 

        self.keep_current_bv = BooleanVar()
        self.keep_current_bv.set(True)

        tk.Checkbutton(frm, text='Retain current keepers?', anchor='w', variable=self.keep_current_bv).grid(row=4, column=0, columnspan=2)

        tk.Button(frm, command=self.ok, text='OK', width=7).grid(row=5, column=0, padx=5)
        tk.Button(frm, command=self.cancel, text='Cancel', width=7).grid(row=5, column=1, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_window()
    
    def update_type(self):
        if self.target_type.get() == 0:
            self.ti_lbl['state'] = DISABLED
            self.ti_entry['state'] = DISABLED  
            self.inflation_sv.set('0.0')
        else:
            self.ti_lbl['state'] = NORMAL
            self.ti_entry['state'] = NORMAL
            self.inflation_sv.set("{:.1f}".format(self.current_inflation))

    def ok(self):
        try:
            self.target_inflation = float(self.inflation_sv.get()) / 100
        except ValueError:
            mb.showwarning('Entered inflation is not a number')
            return
        self.keep_current = self.keep_current_bv.get()
        self.destroy()

    def cancel(self):
        self.target_inflation = None
        self.keep_current = None
        self.destroy()