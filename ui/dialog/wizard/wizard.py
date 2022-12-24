import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb

class Dialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        frm = tk.Frame(self, borderwidth=4)
        
        self.current_step = None
        self.steps=[]

        self.button_frame = tk.Frame(frm, bd=1, relief="raised")
        self.content_frame = tk.Frame(frm)

        self.back_button = tk.Button(self.button_frame, text="<< Back", command=self.back)
        self.next_button = tk.Button(self.button_frame, text="Next >>", command=self.next)
        self.finish_button = tk.Button(self.button_frame, text="Finish", command=self.finish)
        self.cancel_button = tk.Button(self.button_frame, text="Cancel", command=self.cancel)

        self.button_frame.pack(side="bottom", fill="x")
        self.content_frame.pack(side="top", fill="both", expand=True)

        self.show_step(0)

    def show_step(self, step):

        new_step = self.steps[step]

        if self.current_step is not None:
            current_step = self.steps[self.current_step]
            if not current_step.validate():
                 mb.showwarning('Input Error', current_step.validate_msg)
                 return
            if not new_step.on_show():
                mb.showwarning('Error loading page')
                return
            
            # remove current step
            current_step.pack_forget()

        self.current_step = step
        new_step.pack(fill="both", expand=True)

        self.cancel_button.pack(side="left")

        if step == 0:
            # first step
            self.back_button.pack_forget()
            self.next_button.pack(side="right")
            self.finish_button.pack_forget()

        elif step == len(self.steps)-1:
            # last step
            self.back_button.pack(side="left")
            self.next_button.pack_forget()
            self.finish_button.pack(side="right")

        else:
            # all other steps
            self.back_button.pack(side="left")
            self.next_button.pack(side="right")
            self.finish_button.pack_forget()

    def next(self):
        self.show_step(self.current_step + 1)
    
    def back(self):
        self.show_step(self.current_step - 1)
    
    def cancel(self):
        self.destroy()
    
    def finish(self):
        if not self.steps[self.current_step].validate():
            mb.showwarning('Input Error', self.steps[self.current_step].validate_msg)
            return
        self.destroy()