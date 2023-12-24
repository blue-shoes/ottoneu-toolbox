import tkinter as tk     
from tkinter import *              
from tkinter import ttk 

from domain.domain import StartingPosition, StartingPositionSet
from domain.enum import Position
from services import starting_positions_services
from ui.dialog.wizard import wizard

class Dialog(wizard.Dialog):

    starting_set:StartingPositionSet

    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Create Starting Position Set')
        self.starting_set = None

        return self.wizard

class Wizard(wizard.Wizard):
    def __init__(self, parent:Dialog):
        super().__init__(parent)
        self.parent = parent
        self.points_format = False
        self.steps.append(Step0(self))
        self.steps.append(Positions(self))

        self.show_step(0)
    
    def cancel(self):
        self.parent.starting_set = None
        super().cancel()

    def finish(self):
        self.steps[self.current_step].validate()
        self.parent.starting_set = starting_positions_services.save_starting_position_set(self.parent.starting_set)
        super().finish()

class Step0(tk.Frame):
    def __init__(self, parent:Wizard):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text="Initialize Starting Position Set")
        header.grid(row=0, column=0, columnspan=2)

        tk.Label(self, text="Name:").grid(row=1, column=0)
        self.name_tv = StringVar()
        tk.Entry(self, textvariable=self.name_tv).grid(row=1, column=1)

        tk.Label(self, text="Description:").grid(row=2, column=0)
        self.desc_tv = StringVar()
        tk.Entry(self, textvariable=self.desc_tv).grid(row=2, column=1)

    def on_show(self):
        return True
    
    def validate(self):
        self.parent.validate_msg = ''
        if self.name_tv.get() is None or self.name_tv.get() == '':
            self.parent.validate_msg = 'Please input a name'
            return False
        self.parent.parent.starting_set = StartingPositionSet()
        self.parent.parent.starting_set.name = self.name_tv.get()
        self.parent.parent.starting_set.detail = self.desc_tv.get()
        return True

class Positions(tk.Frame):
    def __init__(self, parent:Wizard):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text="Select Positions and Counts").grid(row=0, column=0, columnspan=2)
        self.positions = {}
        self.count_entry = {}
        self.counts = {}
        
        for idx, pos in enumerate(Position.get_offensive_pos() + Position.get_discrete_pitching_pos() + [Position.POS_P]):
            if pos == Position.OFFENSE: continue
            self.positions[pos] = BooleanVar()
            tk.Checkbutton(self, text = pos.value, variable=self.positions[pos], command=lambda _pos=pos: self.toggle_pos(_pos), justify=LEFT, anchor=W).grid(sticky=W, row = (int)(idx/2)+1, column=2*(idx % 2))
            count = StringVar()
            self.counts[pos] = count
            self.count_entry[pos] = ce = tk.Entry(self, textvariable=count)
            ce.grid(row = (int)(idx/2)+1, column=2*(idx % 2)+1)

    def toggle_pos(self, pos:Position):
        if self.positions[pos].get():
            self.count_entry[pos].configure(state='normal')
        else:
            self.count_entry[pos].configure(state='disabled')

    def on_show(self):
        for pos, bv in self.positions.items():
            if pos in [s.position for s in self.parent.parent.starting_set.positions]:
                bv.set(True)
                self.count_entry[pos].configure(state='active')
            else:
                bv.set(False)
                self.count_entry[pos].configure(state='disable')
        return True
    
    def validate(self):
        self.parent.parent.starting_set.positions = []
        found_pos = False
        for pos, bv in self.positions.items():
            if bv.get():
                sp = StartingPosition(position=pos)
                try:
                    sp.count = int(self.counts[pos].get())
                except ValueError:
                    self.parent.validate_msg = 'Point entries must be numbers'
                    return False
                self.parent.parent.starting_set.positions.append(sp)
                found_pos = True
        if found_pos:
            return True
        self.parent.validate_msg = 'Please select at least one position'
        return False