import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent : Toplevel, title):
        super().__init__(parent)
        self.overrideredirect(1)
        tk.Label(self, text=title).grid(row=0,column=0)
        self.progress = 0
        self.progress_var = tk.DoubleVar()
        self.progress_var.set(0)
        ttk.Progressbar(self, variable=self.progress_var, maximum=100).grid(row=1, column=0)
        self.pack_slaves()

        self.progress_step = sv = tk.StringVar()
        self.progress_label = ttk.Label(self, textvariable=self.progress_step)
        self.progress_label.grid(column=0,row=2)

        self.update()
        w = self.winfo_width()
        h = self.winfo_height()
        parent.update()
        x = parent.winfo_x()
        dx = parent.winfo_width()
        y = parent.winfo_y()
        dy = parent.winfo_height()
        self.geometry("+%d+%d" %(x+int(dx/2)-int(w/2), y+int(dy/2)-int(h/2)))
    
    def set_task_title(self, task_title):
        self.progress_step.set(task_title)
        self.update()
    
    def increment_completion_percent(self, increment):
        self.progress += increment
        self.update_completion_percent()
    
    def set_completion_percent(self, percent):
        self.progress = percent
        self.update_completion_percent()
    
    def update_completion_percent(self):
        self.progress_var.set(self.progress)
        self.update()