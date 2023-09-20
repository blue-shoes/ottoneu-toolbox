from tkinter import *              
from tkinter import ttk 

class Table(ttk.Treeview):

    def __init__(self, parent, columns, column_alignments=None, column_widths=None, sortable_columns=None, reverse_col_sort=None, hscroll=True, init_sort_col=None, custom_sort={}, checkbox:bool=False):
        super().__init__(parent, columns=columns, show='headings')

        __checked = PhotoImage('checked', data=b'GIF89a\x0e\x00\x0e\x00\xf0\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x0e\x00\x0e\x00\x00\x02#\x04\x82\xa9v\xc8\xef\xdc\x83k\x9ap\xe5\xc4\x99S\x96l^\x83qZ\xd7\x8d$\xa8\xae\x99\x15Zl#\xd3\xa9"\x15\x00;', master=self)
        __unchecked = PhotoImage('unchecked', data=b'GIF89a\x0e\x00\x0e\x00\xf0\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x0e\x00\x0e\x00\x00\x02\x1e\x04\x82\xa9v\xc1\xdf"|i\xc2j\x19\xce\x06q\xed|\xd2\xe7\x89%yZ^J\x85\x8d\xb2\x00\x05\x00;', master=self)

        self.hscroll = hscroll
        self.reverse_sort = {}
        self.vsb = None
        self.hsb = None
        self.custom_sort = custom_sort
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
            self.column(f"# {col_num}",anchor=align, stretch=NO, width=width)
            if sortable_columns != None:
                if col in sortable_columns:
                    # From https://stackoverflow.com/a/30724912
                    self.heading(col, text=col, command=lambda _col=col: self.treeview_sort_column(_col) )
                    self.reverse_sort[col] = True

                else:
                    self.heading(col, text=col)
                    self.reverse_sort[col] = True
            else:
                self.heading(col, text=col)
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
            self.tag_configure('checked', image='checked')
            self.tag_configure('unchecked', image='unchecked')
            style = ttk.Style(self)
            style.layout('cb.Treeview.Row', [('Treeitem.row',{'sticky':'nswe'}),('Treeitem.image', {'side': 'left', 'sticky':''})])
            self.bind('<ButtonRelease-1>', self.__checkbox_method)
        #self.add_scrollbar()

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
        self.bind('<<TreeviewSelect>>', select_method, add=True)

    def __checkbox_method(self, event):
        """Handle click on items."""
        if len(self.selection()) > 0:
            item = self.selection()[0]
            if event.widget.identify_column(event.x) == '#1':
                # toggle checkbox image
                if self.tag_has('checked', item):
                    self.__tag_remove(item, 'checked')
                    self.__tag_add(item, ('unchecked',))
                else:
                    self.__tag_remove(item, 'unchecked')
                    self.__tag_add(item, ('checked',))
    
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
            l = [(self.set(k, col), k) for k in self.get_children('')]
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
            self.vsb.pack()
        if self.hsb is not None:
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
    try:
        float(v1)
        return float(v1)
    except ValueError:
        return v1