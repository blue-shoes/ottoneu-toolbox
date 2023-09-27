from tkinter import *              
from tkinter import ttk 
from PIL import ImageTk, Image
import sys, os

class Table(ttk.Treeview):

    def __init__(self, parent, columns, column_alignments=None, column_widths=None, sortable_columns=None, reverse_col_sort=None, hscroll=True, init_sort_col=None, custom_sort={}, checkbox:bool=False, pack=True):
        if checkbox:
            super().__init__(parent, columns=columns)
        else:
            super().__init__(parent, columns=columns, show='headings')

        if checkbox:
            self.__checked = ImageTk.PhotoImage(Image.open(resource_path('checked.png')))
            self.__unchecked = ImageTk.PhotoImage(Image.open(resource_path('unchecked.png')))

        self.parent = parent
        self.hscroll = hscroll
        self.reverse_sort = {}
        self.vsb = None
        self.hsb = None
        self.__extra_checkbox_method = None
        self.custom_sort = custom_sort
        self.is_pack = pack
        if checkbox:
            col_num = 0
        else:
            col_num = 1
        self.checkbox = checkbox
        for col in columns:
            align = CENTER
            if column_alignments != None:
                if col in column_alignments:
                    align = column_alignments[col]
            width = 50
            if column_widths != None:
                if col in column_widths:
                    width = column_widths[col]
            self.column(f"#{col_num}",anchor=align, stretch=NO, width=width)
            if sortable_columns != None:
                if col in sortable_columns:
                    # From https://stackoverflow.com/a/30724912
                    self.heading(f'#{col_num}', text=col, command=lambda _col=col: self.treeview_sort_column(_col) )
                    self.reverse_sort[col] = True

                else:
                    self.heading(f'#{col_num}', text=col)
                    self.reverse_sort[col] = True
            else:
                self.heading(f'#{col_num}', text=col)
            col_num += 1
        if reverse_col_sort is not None:
            for col in reverse_col_sort:
                self.reverse_sort[col] = False
        if sortable_columns != None:
            if init_sort_col is None:
                self.sort_col = sortable_columns[0]
            else:
                self.sort_col = init_sort_col
            self.reverse_sort[self.sort_col] = not self.reverse_sort[self.sort_col]
        else:
            self.sort_col = None
        if checkbox:
            self.tag_configure('checked', image=self.__checked)
            self.tag_configure('unchecked', image=self.__unchecked)
            self.bind('<ButtonRelease-1>', self.__checkbox_method)

    def get_row_by_text(self, text):
        if isinstance(text, int):
            text = str(text)
        for child in self.get_children():
            if self.item(child,"text") == text:
                return child
        return None
    
    def set_tags_by_row_text(self, text, tags):
        row = self.get_row_by_text(text)
        if row is not None:
            self.item(row, tags=tags)
    
    def set_right_click_method(self, rclick_method):
        self.bind('<Button-3>', rclick_method)
    
    def set_double_click_method(self, dclick_method):
        self.bind('<Double-Button-1>', dclick_method)
    
    def add_scrollbar(self):
        if self.is_pack:
            self.pack(side='left', fill='both', expand=True)
            if isinstance(self.parent, ScrollableTreeFrame):
                self.vsb = ttk.Scrollbar(self.parent, orient="vertical", command=self.yview)
                self.configure(yscrollcommand=self.vsb.set)
                self.vsb.pack(side='right', fill='y')
                if self.hscroll:
                    self.hsb = ttk.Scrollbar(self.parent.master, orient="horizontal", command=self.xview)
                    self.configure(xscrollcommand=self.hsb.set)
                    self.hsb.pack(side='bottom', fill='x')
            else:
                self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.yview)
                self.configure(yscrollcommand=self.vsb.set)
                self.vsb.pack(side='right', fill='y')
                if self.hscroll:
                    self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.xview)
                    self.configure(xscrollcommand=self.hsb.set)
                    self.hsb.pack(side='bottom', fill='x')
        else:
            self.grid(column=0,row=0, sticky='nsew')
            self.parent.grid_rowconfigure(0, weight=1)
            self.parent.grid_columnconfigure(0, weight=1)

            self.vsb = ttk.Scrollbar(self.parent, orient="vertical", command=self.yview)
            self.configure(yscrollcommand=self.vsb.set)
            self.vsb.grid(row=0, column=1, sticky='ns')
            self.parent.grid_columnconfigure(1, weight=0)

            if self.hscroll:
                self.hsb = ttk.Scrollbar(self.parent, orient="horizontal", command=self.xview)
                self.configure(xscrollcommand=self.hsb.set)
                self.hsb.grid(row=1, column=0, sticky='ew')
                self.parent.grid_rowconfigure(1, weight=0)

    
    def set_refresh_method(self, refresh_method):
        self.refresh_method = refresh_method
    
    def set_row_select_method(self, select_method):            
        self.bind('<<TreeviewSelect>>', select_method, add=True)
    
    def set_checkbox_toggle_method(self, checkbox_method):
        '''The checkbox_method must accept the arguments (iid, selected)'''
        self.__extra_checkbox_method = checkbox_method

    def __checkbox_method(self, event):
        """Handle click on items."""
        if len(self.selection()) > 0:
            item = self.selection()[0]
            if event.widget.identify_column(event.x) == '#0':
                # toggle checkbox image
                if self.tag_has('checked', item):
                    self.__tag_remove(item, 'checked')
                    self.__tag_add(item, ('unchecked',))
                    selected=False
                else:
                    self.__tag_remove(item, 'unchecked')
                    self.__tag_add(item, ('checked',))
                    selected=True
                if self.__extra_checkbox_method is not None:
                    self.__extra_checkbox_method(item, selected)
    
    def __tag_add(self, item, tags):
        new_tags = tuple(self.item(item, 'tags')) + tuple(tags)
        self.item(item, tags=new_tags)

    def __tag_remove(self, item, tag):
        tags = list(self.item(item, 'tags'))
        tags.remove(tag)
        self.item(item, tags=tags)

    def treeview_sort_column(self, col, reverse=None):
        self.sort_col = col
        if reverse is not None:
            self.reverse_sort[col] = reverse
            
        if col in self.custom_sort:
            l = self.custom_sort.get(col)()
        else:
            # From https://stackoverflow.com/a/1967793
            column_index = self["columns"].index(col)
            if self.checkbox:
                column_index -= 1
            l = [(str(self.item(k)["values"][column_index]), k) for k in self.get_children()]
            #l = [(self.set(k, col), k) for k in self.get_children('')]
            l.sort(reverse=self.reverse_sort[col], key=lambda x: sort_cmp(x))

        # rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            self.move(k, '', index)

        # reverse sort next time
        self.reverse_sort[col] = not self.reverse_sort[col]
    
    def refresh(self):
        self.delete(*self.get_children())
        self.refresh_method()
        if self.sort_col is not None:
            self.treeview_sort_column(self.sort_col, not self.reverse_sort[self.sort_col])
        if self.vsb is not None:
            if self.is_pack:
                self.vsb.pack()
        if self.hsb is not None:
            if self.is_pack:
                self.hsb.pack()
    
    def resort(self):
        if self.sort_col is not None:
            self.treeview_sort_column(self.sort_col, not self.reverse_sort[self.sort_col])
    
    def set_display_columns(self, columns):
        self['displaycolumns'] = columns
    
    def hide_columns(self, to_hide):
        new_dc = self['displaycolumns']
        if new_dc == ('#all',):
            new_dc = self['columns']
        new_dc = list(new_dc)
        for col in to_hide:
            if col in new_dc:
                new_dc.remove(col)
        self['displaycolumns'] = tuple(new_dc)

    def show_columns(self, to_show: dict):
        '''Columns to add back to table. Dictionary is column name to desired index'''
        new_dc = self['displaycolumns']
        if new_dc == ('#all',):
            return
        new_dc = list(new_dc)
        for col in to_show:
            if col in new_dc:
                new_dc.append(to_show[col], col)
        self['displaycolumns'] = tuple(new_dc)
    
    def restore_all_columns(self):
        self['displaycolumns'] = ('#all',)

class ScrollableTreeFrame(ttk.Frame):

    table:Table

    def __init__(self, parent, columns, column_alignments=None, column_widths=None, sortable_columns=None, reverse_col_sort=None, hscroll=True, init_sort_col=None, custom_sort={}, checkbox:bool=False, pack=True, **kw):
        super().__init__(parent, **kw)
        if pack:
            self.pack_propagate(False)
        else:
            self.grid_propagate(False)

        if hscroll and pack:
            parent = ttk.Frame(self)
            parent.pack_propagate=False
            parent.pack(side='top', fill='both', expand=True)
        else:
            parent = self

        self.table = Table(parent, columns, column_alignments, column_widths, sortable_columns, reverse_col_sort, hscroll, init_sort_col, custom_sort, checkbox, pack)
        self.table.add_scrollbar()

def bool_to_table(val):
    if val:
        return 'X'
    else:
        return ''
    
def sort_cmp(t1):
    v1 = t1[0]
    if len(v1) == 0:
        return v1
    if v1[0] == '$':
        return float(v1[1:])
    if v1[-1] == '%':
        return float(v1[:-1])
    try:
        float(v1)
        return float(v1)
    except ValueError:
        return v1

def resource_path(end_file) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'resources', end_file) 