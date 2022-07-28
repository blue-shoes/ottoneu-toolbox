import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb

from numpy import sort

class Table(ttk.Treeview):
    def __init__(self, parent, columns, column_alignments=None, column_widths=None, sortable_columns=None):
        super().__init__(parent, columns=columns, show='headings')
        self.sort_col = None
        col_num = 1
        for col in columns:
            align = CENTER
            if column_alignments != None:
                if col in column_alignments:
                    align = column_alignments[col]
            width = 50
            if column_widths != None:
                if col in column_widths:
                    width = column_widths[col]
            self.column(f"# {col_num}",anchor=align, stretch=NO, width=width)
            if sortable_columns != None:
                if col in sortable_columns:
                    self.heading(col, text=col, command=lambda _col=col: self.sort(_col) )
                else:
                    self.heading(col, text=col)
            else:
                self.heading(col, text=col)
            col_num += 1

    
    def set_right_click_method(self, rclick_method):
        self.bind('<Button-3>', rclick_method)
    
    def add_scrollbar(self):
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.yview)
        self.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side='right', fill='y')
    
    def set_refresh_method(self, refresh_method):
        self.refresh_method = refresh_method
    
    def set_row_select_method(self, select_method):
        self.bind('<<TreeviewSelect>>', select_method)
    
    def sort(self, col):
        self.sort_col = sort
        self.refresh()
    
    def refresh(self):
        self.refresh_method()
        self.vsb.pack()
    
    