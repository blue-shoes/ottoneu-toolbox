import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb

from numpy import sort

class Table(ttk.Treeview):
    def __init__(self, parent, columns, column_alignments=None, column_widths=None, sortable_columns=None, hscroll=True):
        super().__init__(parent, columns=columns, show='headings')
        self.sort_col = columns[0]
        self.hscroll = hscroll
        self.reverse_sort = False
        self.vsb = None
        self.hsb = None
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
                    # From https://stackoverflow.com/a/30724912
                    self.heading(col, text=col, command=lambda _col=col: self.treeview_sort_column(_col, False) )
                else:
                    self.heading(col, text=col)
            else:
                self.heading(col, text=col)
            col_num += 1
        #self.add_scrollbar()

    
    def set_right_click_method(self, rclick_method):
        self.bind('<Button-3>', rclick_method)
    
    def add_scrollbar(self):
        self.pack(side='left', fill='both', expand=True)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.yview)
        self.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side='right', fill='y')

        if self.hscroll:
            self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.xview)
            self.configure(xscrollcommand=self.hsb.set)
            self.hsb.pack(side='bottom', fill='x')
    
    def set_refresh_method(self, refresh_method):
        self.refresh_method = refresh_method
    
    def set_row_select_method(self, select_method):
        self.bind('<<TreeviewSelect>>', select_method)
    
    def sort(self, col):
        #TODO: Make sort go ascending and descending
        if self.sort_col == col:
            self.sort_col = None
        else:
            self.sort_col = sort
        self.refresh()
    
    def treeview_sort_column(self, col, reverse):
        self.sort_col = col
        self.reverse_sort = reverse
        # From https://stackoverflow.com/a/1967793
        l = [(self.set(k, col), k) for k in self.get_children('')]
        l.sort(reverse=reverse, key=lambda x: sort_cmp(x))

        # rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            self.move(k, '', index)

        # reverse sort next time
        self.heading(col, command=lambda: \
                self.treeview_sort_column(col, not reverse))
    
    def refresh(self):
        self.delete(*self.get_children())
        self.refresh_method()
        if self.vsb is not None:
            self.vsb.pack()
        if self. hsb is not None:
            self.hsb.pack()

def bool_to_table(val):
    if val:
        return 'X'
    else:
        return ''
    
def sort_cmp(t1):
    v1 = t1[0]
    if v1[0] == '$':
        return float(v1[1:])
    try:
        float(v1)
        return float(v1)
    except ValueError:
        return v1