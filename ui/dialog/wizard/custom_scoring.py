import tkinter as tk
from tkinter import StringVar, IntVar, BooleanVar
from tkinter import W, LEFT

from domain.domain import CustomScoring, CustomScoringCategory
from domain.enum import StatType
from services import custom_scoring_services
from ui.dialog.wizard import wizard


class Dialog(wizard.Dialog):
    scoring: CustomScoring

    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Create Custom Scoring Format')
        self.scoring = None

        return self.wizard


class Wizard(wizard.Wizard):
    def __init__(self, parent: Dialog):
        super().__init__(parent)
        self.parent = parent
        self.points_format = False
        self.steps.append(Step0(self))
        self.steps.append(Hitter_Cats(self))
        self.steps.append(Hitter_Points(self))
        self.steps.append(Pitcher_Cats(self))
        self.steps.append(Pitcher_Points(self))
        # self.steps.append(Confirm(self))

        self.show_step(0)

    def cancel(self):
        self.parent.scoring = None
        super().cancel()

    def determine_next_step(self):
        if self.points_format:
            if self.current_step == 0 or self.current_step == 2:
                return self.current_step + 2
        elif self.current_step == 1 or self.current_step == 3:
            return self.current_step + 2
        return super().determine_next_step()

    def determine_previous_step(self):
        if self.points_format:
            if self.current_step == 4 or self.current_step == 2:
                return self.current_step - 2
        elif self.current_step == 5 or self.current_step == 3:
            return self.current_step - 2
        return super().determine_previous_step()

    def is_last_page(self, step):
        if self.points_format:
            return step == len(self.steps) - 1
        return step == len(self.steps) - 2

    def finish(self):
        self.steps[self.current_step].validate()
        self.parent.scoring = custom_scoring_services.save_scoring_format(self.parent.scoring)
        super().finish()


class Step0(tk.Frame):
    def __init__(self, parent: Wizard):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text='Initialize Scoring Format')
        header.grid(row=0, column=0, columnspan=2)

        tk.Label(self, text='Name:').grid(row=1, column=0)
        self.name_tv = StringVar()
        tk.Entry(self, textvariable=self.name_tv).grid(row=1, column=1)

        tk.Label(self, text='Description:').grid(row=2, column=0)
        self.desc_tv = StringVar()
        tk.Entry(self, textvariable=self.desc_tv).grid(row=2, column=1)

        self.scoring_basis_iv = IntVar()
        self.scoring_basis_iv.set(0)
        tk.Radiobutton(self, text='Categories', variable=self.scoring_basis_iv, value=0).grid(row=3, column=0)
        tk.Radiobutton(self, text='Points', variable=self.scoring_basis_iv, value=1).grid(row=3, column=1)

        self.h2h_bv = BooleanVar()
        self.h2h_bv.set(False)
        tk.Checkbutton(self, text='Head-to-Head?', variable=self.h2h_bv).grid(row=4, column=0)

    def on_show(self):
        return True

    def validate(self):
        self.parent.validate_msg = ''
        if self.name_tv.get() is None or self.name_tv.get() == '':
            self.parent.validate_msg = 'Please input a name'
            return False
        self.parent.parent.scoring = CustomScoring()
        self.parent.parent.scoring.name = self.name_tv.get()
        self.parent.parent.scoring.description = self.desc_tv.get()
        self.parent.parent.scoring.points_format = self.scoring_basis_iv.get() == 1
        self.parent.parent.scoring.head_to_head = self.h2h_bv.get()
        self.parent.points_format = self.parent.parent.scoring.points_format
        return True


class Hitter_Cats(tk.Frame):
    def __init__(self, parent: Wizard):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Select Hitter Categories').grid(row=0, column=0, columnspan=2)
        self.stat_vars = {}

        for idx, stat in enumerate(StatType.get_all_hit_stattype()):
            self.stat_vars[stat] = BooleanVar()
            tk.Checkbutton(self, text=stat.display, variable=self.stat_vars[stat], justify=LEFT, anchor=W).grid(sticky=W, row=(int)(idx / 2) + 1, column=idx % 2)

    def on_show(self):
        for stat, bv in self.stat_vars.items():
            if stat in [s.category for s in self.parent.parent.scoring.stats]:
                bv.set(True)
            else:
                bv.set(False)
        return True

    def validate(self):
        if self.parent.parent.scoring.stats is None:
            self.parent.parent.scoring.stats = []
        to_remove = []
        for csc in self.parent.parent.scoring.stats:
            if csc.category.hitter:
                to_remove.append(csc)
        self.parent.parent.scoring.stats = [s for s in self.parent.parent.scoring.stats if s not in to_remove]
        found_cat = False
        for stat, bv in self.stat_vars.items():
            if bv.get():
                csc = CustomScoringCategory()
                csc.category = stat
                self.parent.parent.scoring.stats.append(csc)
                found_cat = True
        if found_cat:
            return True
        self.parent.validate_msg = 'Please select at least one stat category'
        return False


class Hitter_Points(tk.Frame):
    def __init__(self, parent: Wizard):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Select Hitter Categories').grid(row=0, column=0, columnspan=2)
        self.stat_vars = {}
        self.point_entries = {}
        self.stat_points = {}

        for idx, stat in enumerate(StatType.get_all_hit_stattype()):
            self.stat_vars[stat] = BooleanVar()
            tk.Checkbutton(self, text=stat.display, variable=self.stat_vars[stat], command=lambda _stat=stat: self.toggle_stat(_stat), justify=LEFT, anchor=W).grid(
                sticky=W, row=(int)(idx / 2) + 1, column=2 * (idx % 2)
            )
            points = StringVar()
            self.stat_points[stat] = points
            self.point_entries[stat] = sp = tk.Entry(self, textvariable=points)
            sp.grid(row=(int)(idx / 2) + 1, column=2 * (idx % 2) + 1)

    def toggle_stat(self, stat: StatType):
        if self.stat_vars[stat].get():
            self.point_entries[stat].configure(state='active')
        else:
            self.point_entries[stat].configure(state='disable')

    def on_show(self):
        for stat, bv in self.stat_vars.items():
            if stat in [s.category for s in self.parent.parent.scoring.stats]:
                bv.set(True)
                self.point_entries[stat].configure(state='active')
            else:
                bv.set(False)
                self.point_entries[stat].configure(state='disable')
        return True

    def validate(self):
        if self.parent.parent.scoring.stats is None:
            self.parent.parent.scoring.stats = []
        to_remove = []
        for csc in self.parent.parent.scoring.stats:
            if csc.category.hitter:
                to_remove.append(csc)
        self.parent.parent.scoring.stats = [s for s in self.parent.parent.scoring.stats if s not in to_remove]
        found_cat = False
        for stat, bv in self.stat_vars.items():
            if bv.get():
                csc = CustomScoringCategory()
                csc.category = stat
                try:
                    csc.points = float(self.stat_points[stat].get())
                except ValueError:
                    self.parent.validate_msg = 'Point entries must be numbers'
                    return False
                self.parent.parent.scoring.stats.append(csc)
                found_cat = True
        if found_cat:
            return True
        self.parent.validate_msg = 'Please select at least one stat category'
        return False


class Pitcher_Cats(tk.Frame):
    def __init__(self, parent: Wizard):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Select Pitcher Categories').grid(row=0, column=0, columnspan=2)
        self.stat_vars = {}

        for idx, stat in enumerate(StatType.get_all_pitch_stattype(no_rates=False)):
            self.stat_vars[stat] = BooleanVar()
            tk.Checkbutton(self, text=stat.display, variable=self.stat_vars[stat], justify=LEFT, anchor=W).grid(sticky=W, row=(int)(idx / 2) + 1, column=idx % 2)

    def on_show(self):
        for stat, bv in self.stat_vars.items():
            if stat in [s.category for s in self.parent.parent.scoring.stats]:
                bv.set(True)
            else:
                bv.set(False)
        return True

    def validate(self):
        if self.parent.parent.scoring.stats is None:
            self.parent.parent.scoring.stats = []
        to_remove = []
        for csc in self.parent.parent.scoring.stats:
            if not csc.category.hitter:
                to_remove.append(csc)
        self.parent.parent.scoring.stats = [s for s in self.parent.parent.scoring.stats if s not in to_remove]
        found_cat = False
        for stat, bv in self.stat_vars.items():
            if bv.get():
                csc = CustomScoringCategory()
                csc.category = stat
                self.parent.parent.scoring.stats.append(csc)
                found_cat = True
        if found_cat:
            return True
        self.parent.validate_msg = 'Please select at least one stat category'
        return False


class Pitcher_Points(tk.Frame):
    def __init__(self, parent: Wizard):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Select Pitcher Categories').grid(row=0, column=0, columnspan=2)
        self.stat_vars = {}
        self.point_entries = {}
        self.stat_points = {}

        for idx, stat in enumerate(StatType.get_all_pitch_stattype(no_rates=True)):
            self.stat_vars[stat] = BooleanVar()
            tk.Checkbutton(self, text=stat.display, variable=self.stat_vars[stat], command=lambda _stat=stat: self.toggle_stat(_stat), justify=LEFT, anchor=W).grid(
                sticky=W, row=(int)(idx / 2) + 1, column=2 * (idx % 2)
            )
            points = StringVar()
            self.stat_points[stat] = points
            self.point_entries[stat] = sp = tk.Entry(self)
            sp.grid(row=(int)(idx / 2) + 1, column=2 * (idx % 2) + 1)

    def toggle_stat(self, stat: StatType):
        if self.stat_vars[stat].get():
            self.point_entries[stat].configure(state='active')
        else:
            self.point_entries[stat].configure(state='disable')

    def on_show(self):
        for stat, bv in self.stat_vars.items():
            if stat in [s.category for s in self.parent.parent.scoring.stats]:
                bv.set(True)
                self.point_entries[stat].configure(state='active')
            else:
                bv.set(False)
                self.point_entries[stat].configure(state='disable')
        return True

    def validate(self):
        if self.parent.parent.scoring.stats is None:
            self.parent.parent.scoring.stats = []
        to_remove = []
        for csc in self.parent.parent.scoring.stats:
            if not csc.category.hitter:
                to_remove.append(csc)
        self.parent.parent.scoring.stats = [s for s in self.parent.parent.scoring.stats if s not in to_remove]
        found_cat = False
        for stat, bv in self.stat_vars.items():
            if bv.get():
                csc = CustomScoringCategory()
                csc.category = stat
                try:
                    csc.points = float(self.stat_points[stat].get())
                except ValueError:
                    self.parent.validate_msg = 'Point entries must be numbers'
                    return False
                self.parent.parent.scoring.stats.append(csc)
                found_cat = True
        if found_cat:
            return True
        self.parent.validate_msg = 'Please select at least one stat category'
        return False
