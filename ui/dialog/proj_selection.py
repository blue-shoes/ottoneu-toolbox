import tkinter as tk     
from tkinter import *              
from tkinter import ttk 

from services import projection_services

class Dialog:
    def __init__(self):
        self.top = top = tk.Toplevel(None)
        top.title("Select a Projection")
        frm = tk.Frame(top, borderwidth=4)

