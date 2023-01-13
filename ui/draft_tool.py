import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from tkinter.messagebox import OK
import os
import os.path
import pandas as pd
import numpy as np
import util.string_util
import queue
import logging
import math

from scrape.scrape_ottoneu import Scrape_Ottoneu 
from domain.enum import Position, ScoringFormat, StatType, Preference as Pref, AvgSalaryFom
from ui.table import Table
from ui.dialog import progress, draft_target
from services import salary_services, league_services, calculation_services, player_services, draft_services
from demo import draft_demo

import threading
from time import sleep
from datetime import datetime, timedelta

from enum import Enum

class IdType(Enum):
    OTTONEU = 0
    FG = 1

class DraftTool(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.demo_source = controller.demo_source
        self.demo_thread = None
        self.run_event = controller.run_event
        self.queue = queue.Queue()
        self.sort_cols = {}
        self.show_drafted_players = tk.BooleanVar()
        self.show_drafted_players.set(False)
        self.show_removed_players = tk.BooleanVar()
        self.show_removed_players.set(False)
        self.search_unrostered_bv = tk.BooleanVar()
        self.search_unrostered_bv.set(False)
        self.targeted_players = pd.DataFrame()
        self.removed_players = []
        self.league = None
        self.value_calculation = None

        self.create_main()
    
    def on_show(self):
        if self.controller.league is None or not league_services.league_exists(self.controller.league):
            self.controller.select_league()
        if self.controller.value_calculation is None or len(self.controller.value_calculation.values) == 0:
            self.controller.select_value_set()
        if self.controller.league is None or self.controller.value_calculation is None:
            return False
        
        same_values = self.value_calculation == self.controller.value_calculation

        self.league = self.controller.league
        self.value_calculation = self.controller.value_calculation
        self.league_text_var.set(f'{self.controller.league.name} Draft')

        self.calculate_extra_value()

        pd = progress.ProgressDialog(self, title='Downloading latest salary information...')
        pd.increment_completion_percent(10)
        #if len(self.salary_update) == 0 and (datetime.now() - salary_services.get_last_refresh().last_refresh) > timedelta(days=1):
        if (datetime.now() - salary_services.get_last_refresh().last_refresh) > timedelta(days=1):
            salary_services.update_salary_info()
        pd.increment_completion_percent(50)

        format_salary_refresh = salary_services.get_last_refresh(self.controller.league.format)
        if format_salary_refresh is None or (datetime.now() - format_salary_refresh.last_refresh) > timedelta(days=1):
            salary_services.update_salary_info(format=self.league.format)
        pd.complete()

        self.draft = draft_services.get_draft_by_league(self.controller.league.index)

        self.initialize_draft(same_values)

        #Clean up previous demo run
        if os.path.exists(draft_demo.demo_trans):
            os.remove(draft_demo.demo_trans)

        return True

    def leave_page(self):
        return True

    def calculate_extra_value(self):
        captured_value = 0
        self.valued_roster_spots = 0
        for pv in self.value_calculation.values:
            if pv.position != Position.OVERALL or pv.value < 1:
                continue
            captured_value += pv.value
            self.valued_roster_spots += 1
        self.extra_value = self.league.num_teams * 400 - captured_value

    def create_main(self):
        self.league_text_var = StringVar()
        if self.controller.league is None:
            self.league_text_var.set("Draft")
        else:
            self.league_text_var.set(f'League {self.controller.league.name} Draft')
        self.lg_lbl = ttk.Label(self, textvariable=self.league_text_var, font='bold')
        self.lg_lbl.grid(column=0,row=0, pady=5, columnspan=2)

        running_list_frame = ttk.Frame(self, border=4)
        running_list_frame.grid(row=2, column=0, columnspan=2, pady=5)

        self.tab_control = ttk.Notebook(running_list_frame, width=570, height=300)
        self.tab_control.grid(row=0, column=0)

        self.create_search()

        button_frame = ttk.Frame(running_list_frame)
        button_frame.grid(row=0, column=1, sticky=tk.N, pady=15)

        show_drafted_btn = ttk.Checkbutton(button_frame, text="Show rostered players?", variable=self.show_drafted_players, command=self.refresh_views)
        show_drafted_btn.grid(row=0, column=1, sticky=tk.NW, pady=5)
        show_drafted_btn.state(['!alternate'])

        show_removed_btn = ttk.Checkbutton(button_frame, text="Show removed players?", variable=self.show_removed_players, command=self.refresh_views)
        show_removed_btn.grid(row=1, column=1, sticky=tk.NW)
        show_removed_btn.state(['!alternate'])

        self.pos_view = {}

        overall_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(overall_frame, text='Overall')
        cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G','P/IP', 'Avg. Price', 'L10 Price', 'Roster %')
        sortable_cols = ('Name', 'Value', 'Inf. Cost', 'Points', 'P/G', 'P/IP', 'Avg. Price', 'L10 Price', 'Roster %')
        rev_sort_cols = ('Value', 'Inf. Cost', 'Points', 'P/G', 'P/IP', 'Avg. Price', 'L10 Price', 'Roster %')
        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W
        self.overall_view = ov = Table(overall_frame, cols,sortable_columns=sortable_cols, column_widths=widths, init_sort_col='Value', column_alignments=align)
        ov.grid(column=0)
        ov.set_row_select_method(self.on_select)
        ov.set_right_click_method(self.player_rclick)
        self.set_row_colors(ov)
        ov.add_scrollbar()
        ov.set_refresh_method(self.refresh_overall_view)

        for pos in (Position.get_offensive_pos() + Position.get_pitching_pos()):
            pos_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(pos_frame, text=pos.value) 
            if pos in Position.get_offensive_pos():
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G', 'Avg. Price', 'L10 Price', 'Roster %')
            else:
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/IP', 'Avg. Price', 'L10 Price', 'Roster %')
            self.pos_view[pos] = pv = Table(pos_frame, cols,sortable_columns=sortable_cols, column_widths=widths, column_alignments=align, init_sort_col='Value')
            pv.grid(column=0)
            pv.set_row_select_method(self.on_select)
            pv.set_right_click_method(self.player_rclick)
            self.set_row_colors(pv)
            pv.set_refresh_method(lambda _pos = pos: self.refresh_pos_table(_pos))
            pv.add_scrollbar()
        
        if self.controller.preferences.getboolean('Draft', Pref.DOCK_DRAFT_TARGETS, fallback=False):
            target_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(target_frame, text='Targets')
        else:
            planning_frame = ttk.Frame(self)
            planning_frame.grid(row=2, column=2)

            self.planning_tab = ptab = ttk.Notebook(planning_frame, width=570, height=300)
            ptab.grid(row=0, column=0)

            target_frame = ttk.Frame(ptab)
            ptab.add(target_frame, text='Targets')

        cols=['Name', 'Target Price', 'Value', 'Pos']
        rev_sort = ['Target Price', 'Value']

        self.target_table = tt = Table(target_frame, columns=cols, column_alignments=align, 
            column_widths=widths, sortable_columns=cols, reverse_col_sort=rev_sort, init_sort_col='Value')
        tt.grid(column=0)
        tt.set_row_select_method(self.on_select)
        tt.set_right_click_method(self.target_rclick)
        self.set_row_colors(tt, targets=False)
        tt.set_refresh_method(self.refresh_targets)
        tt.add_scrollbar()
    
    def create_search(self):
        if self.controller.preferences.getboolean('Draft', Pref.DOCK_DRAFT_PLAYER_SEARCH):
            monitor_frame = ttk.Frame(self)
            monitor_frame.grid(row=1, column=0, columnspan=2)
            self.start_monitor = ttk.Button(monitor_frame, text='Start Draft', command=self.start_draft_monitor).grid(column=0,row=0)
            self.monitor_status = tk.StringVar()
            self.monitor_status.set('Not started')
            self.monitor_status_lbl = tk.Label(monitor_frame, textvariable=self.monitor_status, fg='red')
            self.monitor_status_lbl.grid(column=2,row=0)
            self.stop_monitor = ttk.Button(monitor_frame, text="Stop Draft", command=self.stop_draft_monitor).grid(column=1,row=0)

            self.inflation_str_var = tk.StringVar()

            self.inflation_lbl = ttk.Label(monitor_frame, textvariable=self.inflation_str_var)
            self.inflation_lbl.grid(column=3,row=0)

            search_frame = ttk.Frame(self.tab_control, border=4)
            self.tab_control.add(search_frame, text='Search')
            #search_frame.grid(column=0)
            ttk.Label(search_frame, text = 'Search:').grid(column=0,row=0,pady=5)

            self.search_string = ss = tk.StringVar()
            ss.trace("w", lambda name, index, mode, sv=ss: self.search_view.refresh())
            ttk.Entry(search_frame, textvariable=ss).grid(column=1,row=0)

            f = ttk.Frame(search_frame, border=4)
            f.grid(column=0,row=1, columnspan=3)

            self.create_search_table(f, 0, 0)

            #search_unrostered_btn = ttk.Checkbutton(search_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv)
            search_unrostered_btn = ttk.Checkbutton(search_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv, command=self.search_view.refresh)
            search_unrostered_btn.grid(row=0, column=2, sticky=tk.NW, pady=5)
            search_unrostered_btn.state(['!alternate'])
        
        else:

            search_frame = ttk.Frame(self)
            search_frame.grid(column=0,row=1, padx=5, sticky=tk.N, pady=17)
            ttk.Label(search_frame, text = 'Player Search: ', font='bold').grid(column=0,row=1,pady=5)

            self.search_string = ss = tk.StringVar()
            ss.trace("w", lambda name, index, mode, sv=ss: self.search_view.refresh())
            ttk.Entry(search_frame, textvariable=ss).grid(column=1,row=1)

            self.start_monitor = ttk.Button(search_frame, text='Start Draft Monitor', command=self.start_draft_monitor).grid(column=0,row=3)
            self.monitor_status = tk.StringVar()
            self.monitor_status.set('Monitor not started')
            self.monitor_status_lbl = tk.Label(search_frame, textvariable=self.monitor_status, fg='red')
            self.monitor_status_lbl.grid(column=1,row=3)
            self.stop_monitor = ttk.Button(search_frame, text="Stop Draft Monitor", command=self.stop_draft_monitor).grid(column=0,row=4)

            self.inflation_str_var = tk.StringVar()

            self.inflation_lbl = ttk.Label(search_frame, textvariable=self.inflation_str_var)
            self.inflation_lbl.grid(column=0,row=5)

            f = ttk.Frame(self)
            f.grid(column=1,row=1)
            
            ttk.Label(f, text = 'Search Results', font='bold').grid(column=0, row=0)

            self.create_search_table(f, col=0, row=1)

            search_unrostered_btn = ttk.Checkbutton(search_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv, command=self.search_view.refresh)
            search_unrostered_btn.grid(row=2, column=1, sticky=tk.NW, pady=5)
            search_unrostered_btn.state(['!alternate'])
    
    def create_search_table(self, parent, col, row, col_span=1):
        cols = ('Name','Value','Salary','Inf. Cost','Pos','Team','Points','P/G','P/IP', 'Roster %')
        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W
        custom_sort = {}
        custom_sort['Value'] = self.default_search_sort
        self.search_view = sv = Table(parent, columns=cols, column_alignments=align, column_widths=widths, sortable_columns=cols, init_sort_col='Value', custom_sort=custom_sort)    
        self.search_view.grid(column=col,row=row, padx=5, columnspan=col_span)   
        sv.set_row_select_method(self.on_select)
        sv.set_right_click_method(self.player_rclick)
        self.set_row_colors(sv)
        sv.set_refresh_method(self.update_player_search)

    def target_rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        playerid = int(event.widget.item(event.widget.selection()[0])["text"])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Change Target Price", command=lambda: self.target_player(playerid))
        popup.add_command(label="Remove Target", command=lambda: self.remove_target(playerid))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def player_rclick(self, event):
        iid = event.widget.identify_row(event.y)
        event.widget.selection_set(iid)
        playerid = int(event.widget.item(event.widget.selection()[0])["text"])
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Target Player", command=lambda: self.target_player(int(playerid)))
        popup.add_separator()
        if playerid in self.removed_players:
            popup.add_command(label='Restore Player', command=lambda: self.restore_player(int(playerid)))
        else:
            popup.add_command(label='Remove Player', command=lambda: self.remove_player(int(playerid)))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def target_player(self, playerid):
        target = self.draft.get_target_by_player(playerid)
        if target is None:
            dialog = draft_target.Dialog(self, playerid)
            if dialog.status == OK:
                target = draft_services.create_target(self.draft, playerid, dialog.price)
                self.draft.targets.append(target)
        else: 
            dialog = draft_target.Dialog(self, playerid, target.price)
            if dialog.status == OK:
                draft_services.update_target(target, dialog.price)
                self.draft.set_target(playerid, dialog.price)
        if dialog.status == OK:
            self.refresh_planning_frame()
    
    def remove_target(self, playerid):
        target = self.draft.get_target_by_player(playerid)
        self.draft.targets.remove(target)
        draft_services.delete_target(target)
        self.refresh_planning_frame()
    
    def remove_player(self, playerid):
        self.removed_players.append(playerid)
        self.refresh_views()
    
    def restore_player(self, playerid):
        self.removed_players.remove(playerid)
        self.refresh_views()

    def sort_treeview(self, treeview, col, pos=None):
        if self.sort_cols[treeview] == col:
            self.sort_cols[treeview] = None
        else:
            self.sort_cols[treeview] = col
        if pos != None:
            self.refresh_pos_table(pos)
        else:
            self.refresh_overall_view()

    def on_select(self, event):
        if len(event.widget.selection()) == 1:
            print(f'Selection is {int(event.widget.item(event.widget.selection()[0])["text"])}')
    
    def default_search_sort(self):
        l = [((self.search_view.set(k, 'Value'), self.search_view.set(k,'Roster %')), k) for k in self.search_view.get_children('')]
        l = sorted(l, reverse=self.search_view.reverse_sort['Value'], key=lambda x: self.sort_search_val_and_rost(x))
        return l
    
    def sort_search_val_and_rost(self, val_rost):
        val = float(val_rost[0][0][1:])
        rost = float(val_rost[0][1][:-1])
        return (val, rost)

    def start_draft_monitor(self):
        logging.info('---Starting Draft Monitor---')
        self.run_event.set()
        self.monitor_thread = threading.Thread(target = self.refresh_thread)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.monitor_status.set('Draft Started')
        self.monitor_status_lbl.config(fg='green')
        self.parent.update_idletasks()
        self.parent.after(1000, self.update_ui)

        if self.demo_source:
            self.demo_thread = threading.Thread(target=draft_demo.demo_draft, args=(self.league, self.run_event))
            self.demo_thread.daemon = True
            self.demo_thread.start()


    def update_ui(self):
        if not self.run_event.is_set and self.queue.empty():
            return
        if not self.queue.empty():
            key, data = self.queue.get()
            logging.debug(f'Updating the following positions: {data}')
            self.refresh_views(data)
        self.parent.after(1000, self.update_ui)
    
    def stop_draft_monitor(self):
        logging.info('!!!Stopping Draft Monitor!!!')
        self.run_event.clear()
        self.monitor_status.set('Draft stopped')
        self.monitor_status_lbl.config(fg='red')
        self.parent.update_idletasks()
    
    def add_trans_to_rosters(self, last_trans, index, player):
        row=last_trans.iloc[index]
        if row['Salary'] == '$0':
            # Cut
            self.rosters.drop(player.index)
        else:
            self.rosters.loc[player.index] = [row['Team ID'],row['Ottoneu ID'],int(row['Salary'].split('$')[1])]

    def refresh_thread(self):
        last_time = datetime.now() - timedelta(minutes=30)
        delay = 45
        if self.demo_source:
            last_time = datetime.now() - timedelta(days=10)
            #speed up loop refresh for demo
            delay = 10
        while(self.run_event.is_set()):
            if not self.demo_source:
                last_trans = Scrape_Ottoneu().scrape_recent_trans_api(self.controller.league.ottoneu_id)
            else:
                logging.debug("demo_source")
                if not os.path.exists(draft_demo.demo_trans):
                    sleep(11)
                    continue
                last_trans = pd.read_csv(draft_demo.demo_trans)
                last_trans['Date'] = last_trans['Date'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f'))
            most_recent = last_trans.iloc[0]['Date']
            if most_recent > last_time:
                index = len(last_trans)-1
                update_pos = []
                while index >= 0:
                    if last_trans.iloc[index]['Date'] > last_time:
                        otto_id = last_trans.iloc[index]['Ottoneu ID']
                        player = player_services.get_player_by_ottoneu_id(int(otto_id))
                        if player is None:
                            logging.info(f'Otto id {otto_id} not in database')
                            index -= 1
                            continue
                        else:
                            self.add_trans_to_rosters(last_trans, index, player)
                        if not player.index in self.values.index:
                            logging.info(f'id {player.index} not in values')
                            index -= 1
                            continue
                        pos = player_services.get_player_positions(player)
                        update_pos = np.append(update_pos, pos)
                        if last_trans.iloc[index]['Type'].upper() == 'ADD':
                            salary = int(last_trans.iloc[index]['Salary'].split('$')[1])
                            self.values.at[player.index, 'Salary'] = salary
                            for p in pos:                                    
                                self.pos_values[p].at[player.index, 'Salary'] = salary
                        elif last_trans.iloc[index]['Type'].upper() == 'CUT':
                            self.values.at[player.index, 'Salary'] = 0
                            for p in pos:
                                self.pos_values[p].at[player.index, 'Salary'] = 0
                    index -= 1
                last_time = most_recent
                self.queue.put(('pos', list(set(update_pos))))
            sleep(delay)

    def sort_df_by(self, df, col):
        if col == 'Value':
            if 'Blank col 0' in df:
                return df.sort_values(by=['Blank col 0'], ascending=[False])
            else:
                return df.sort_values(by=['PAR'], ascending=[False])
        if col == 'Points':
            return df.sort_values(by=['Points'], ascending=[False])
        if col == 'P/G':
            return df.sort_values(by=['P/G'], ascending=[False])
        if col == 'P/IP':
            return df.sort_values(by=['P/IP'], ascending=[False])

    def refresh_views(self, pos_keys=None):
        self.calc_inflation()
        self.overall_view.refresh()
        if pos_keys == None:
            for pos in (Position.get_offensive_pos() + Position.get_pitching_pos()):
                self.pos_view[pos].refresh()
        else:
            for pos in pos_keys:
                logging.debug(f'updating {pos.value}')
                self.pos_view[pos].refresh()
        
        self.search_view.refresh()
        self.refresh_planning_frame()
    
    def refresh_overall_view(self):
        if self.show_drafted_players.get() == 1:
            pos_df = self.values
        else:
            pos_df = self.values.loc[self.values['Salary'] == 0]
        for i in range(len(pos_df)):
            id = pos_df.index[i]
            if id in self.removed_players and not self.show_removed_players.get():
                continue
            name = pos_df.iat[i, 2]
            value = '$' + "{:.0f}".format(pos_df.iat[i, 1])
            inf_cost = '$' + "{:.0f}".format(pos_df.iat[i, 1] * self.inflation)
            position = pos_df.iat[i, 4]
            team = pos_df.iat[i, 3]
            pts = "{:.1f}".format(pos_df.iat[i, 5])
            ppg = "{:.2f}".format(pos_df.iat[i, 7])
            pip = "{:.2f}".format(pos_df.iat[i, 8])
            salary = f'${int(pos_df.iat[i, 10])}'
            sal_tup = self.get_salary_tuple(int(id))
            tags = self.get_row_tags(id)
            self.overall_view.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, ppg, pip, sal_tup[0], sal_tup[1], sal_tup[2]), tags=tags)

    def refresh_pos_table(self, pos):
        if self.show_drafted_players.get() == 1:
            pos_df = self.pos_values[pos]
        else:
            pos_df = self.pos_values[pos].loc[self.pos_values[pos]['Salary'] == 0]
        for i in range(len(pos_df)):
            id = pos_df.index[i]
            if id in self.removed_players and self.show_removed_players.get() != 1:
                continue
            name = pos_df.iat[i, 2]
            value = '$' + "{:.0f}".format(pos_df.iat[i, 1])
            inf_cost = '$' + "{:.0f}".format(pos_df.iat[i, 1] * self.inflation)
            position = pos_df.iat[i, 4]
            team = pos_df.iat[i, 3]
            pts = "{:.1f}".format(pos_df.iat[i, 5])
            rate = "{:.2f}".format(pos_df.iat[i, 7])
            salary = f'${int(pos_df.iat[i, 8])}'
            tags = self.get_row_tags(id)
            sal_tup = self.get_salary_tuple(int(id))

            self.pos_view[pos].insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, rate, sal_tup[0], sal_tup[1], sal_tup[2]), tags=tags)

    def get_salary_tuple(self, playerid):
        si = self.value_calculation.get_player_value(playerid, pos=Position.OVERALL).player.get_salary_info_for_format(self.league.format)
        if si is None:
            avg = '$0.0'
            l10 = '$0.0'
            roster = '0.0%'
        else:
            if self.controller.preferences.get('General', Pref.AVG_SALARY_FOM) == AvgSalaryFom.MEAN.value:
                avg = f'$' + "{:.1f}".format(si.avg_salary)
            else:
                avg = f'$' + "{:.1f}".format(si.med_salary)
            l10 = f'$' + "{:.1f}".format(si.last_10)
            roster = "{:.1f}".format(si.roster_percentage) + '%'
        return (avg, l10, roster)

    def get_row_tags(self, playerid):
        if playerid in self.rosters.index:
            return ('rostered',)
        if self.draft.get_target_by_player(player_id=playerid) is not None:
            return ('targeted',)
        if playerid in self.removed_players:
            return ('removed',)
        return ''
    
    def set_row_colors(self, table, targets=True):
        table.tag_configure('rostered', background='#A6A6A6')
        table.tag_configure('rostered', foreground='#5A5A5A')
        table.tag_configure('removed', background='#FFCCCB')
        if targets:
            table.tag_configure('targeted', background='#FCE19D')

    def update_player_search(self):
        text = self.search_string.get().upper()
        if text == '' or len(text) == 1:
            players = [] 
        else:
            players = player_services.search_by_name(text)
        for player in players:
            si = player.get_salary_info_for_format(self.league.format)
            if si is None and not self.search_unrostered_bv.get():
                continue
            id = player.index
            name = player.name
            pos = player.position
            team = player.team
            if id in self.values.index:
                value = self.value_calculation.get_player_value(id, Position.OVERALL).value
                inf_cost = '$' + "{:.0f}".format(value * self.inflation)
                value = '$' + "{:.0f}".format(value)
            else:
                value = '$0'
                inf_cost = '$0'
            if id in self.rosters.index:
                salary = f"${int(self.rosters.at[id, 'Salary'])}"
            else:
                salary = '$0'
            pp = self.value_calculation.projection.get_player_projection(id)
            if pp is not None:
                h_pts = calculation_services.get_points(pp, Position.OFFENSE)
                p_pts = calculation_services.get_points(pp, Position.PITCHER, ScoringFormat.is_sabr(self.league.format))
                pts = "{:.1f}".format(h_pts + p_pts)
                ppg = "{:.2f}".format(calculation_services.get_batting_point_rate_from_player_projection(pp))
                pip = "{:.2f}".format(calculation_services.get_pitching_point_rate_from_player_projection(pp, self.league.format))
            else:
                pts = '0.0'
                ppg = '0.00'
                pip = '0.00'
            
            if si is None:
                roster_percent = '0.0%'
            else:
                roster_percent = "{:.1f}".format(si.roster_percentage) + "%"

            tags = self.get_row_tags(id)
            self.search_view.insert('', tk.END, text=id, tags=tags, values=(name, value, salary, inf_cost,pos, team, pts, ppg, pip, roster_percent))
   
    def refresh_planning_frame(self):
        self.target_table.refresh()

    def refresh_targets(self):
        for target in self.draft.targets:
            id = target.player_id
            name = target.player.name
            t_price = f'${target.price}'
            value = '$' + "{:.0f}".format(self.value_calculation.get_player_value(id, pos=Position.OVERALL).value)
            pos = target.player.position
            tags = self.get_row_tags(id)
            self.target_table.insert('', tk.END, text=id, tags=tags, values=(name, t_price, value, pos))

    def create_setup_tab(self, tab):
        try:
            ttk.Label(tab, text = "Enter League #:").grid(column=0,row=0, pady=5, sticky=tk.E)
            #width is in text units, not pixels
            self.league_num_entry = ttk.Entry(tab, width = 10)
            self.league_num_entry.grid(column=1,row=0, sticky=tk.W, padx=5)
            ttk.Label(tab, text = "Player Values Directory:").grid(column=0,row=1, pady=5, stick=tk.E)
            self.dir_button = ttk.Button(tab, textvariable = self.value_dir, command=self.select_dir)
            self.dir_button.grid(column=1,row=1, padx=5)

            ttk.Button(tab, text='Initialize Session', command=self.initialize_draft).grid(column=1,row=2, pady=5, sticky=tk.W, padx=5)

            tab.pack()
        except Exception as e:
            logging.exception('Error creating draft')
            mb.showerror("Draft Error", f'Error creating draft, see ./logs/draft.log')

    def select_dir(self):
        filetypes = (
            ('csv files', '*.csv'),
            ('All files', '*.*')
        )

        dir = fd.askdirectory(
            title='Choose a directory',
            initialdir=self.value_dir.get())

        value_file = os.path.join(dir, 'values.csv')
        
        if not os.path.exists(value_file):
            value_file = os.path.join(dir, 'ottoneu_values.csv')
            if not os.path.exists(value_file):
                mb.showinfo('Bad Directory', f'The directory {dir} does not contain a values.csv or ottoneu_values.csv file. Please select a different directory.')
                return

        self.value_dir.set(dir)
        
    def initialize_draft(self, same_values=False):  
        restart = False
        if self.run_event.is_set():
            self.stop_draft_monitor()
        pd = progress.ProgressDialog(self.parent, 'Initializing Draft Session')
        pd.set_task_title('Loading Rosters...')
        pd.set_completion_percent(5)
        self.create_roster_df()    
        pd.set_task_title('Loading Values...')
        pd.increment_completion_percent(10)  
        if not same_values:
            self.create_overall_df_from_vc()
            pd.increment_completion_percent(10)
            self.pos_values = {}
            for pos in Position.get_offensive_pos():
                self.pos_values[pos] = self.create_offensive_df(pos)
                pd.increment_completion_percent(5)
            for pos in Position.get_pitching_pos():
                self.pos_values[pos] = self.create_pitching_df(pos)
                pd.increment_completion_percent(5)
        else:
            self.values.drop('Salary', axis=1, inplace=True)
            for pos in Position.get_offensive_pos():
                self.pos_values[pos].drop('Salary', axis=1, inplace=True)
                pd.increment_completion_percent(5)
            for pos in Position.get_pitching_pos():
                self.pos_values[pos].drop('Salary', axis=1, inplace=True)
                pd.increment_completion_percent(5)

        pd.set_task_title('Updating available players...')
        self.update_rostered_players()
        pd.increment_completion_percent(5)
        pd.set_task_title('Refreshing views...')
        self.refresh_views()
        pd.complete()
        if restart:
            self.start_draft_monitor()
    
    def create_roster_df(self):
        rows = self.get_roster_rows()
        if len(rows) == 0:
            self.rosters = pd.DataFrame(columns= ['index', 'TeamID', 'ottoneu ID', 'Salary'])
        else:
            self.rosters = pd.DataFrame(rows)
            self.rosters.columns = ['index', 'TeamID', 'ottoneu ID', 'Salary']
        self.rosters.set_index('index', inplace=True)
    
    def get_roster_rows(self):
        rows = []
        for team in self.league.teams:
            for rs in team.roster_spots:
                row = []
                row.append(rs.player.index)
                row.append(team.index)
                row.append(rs.player.ottoneu_id)
                row.append(rs.salary)
                rows.append(row)
        return rows
    
    def create_overall_df_from_vc(self):
        rows = self.get_overall_value_rows()
        self.values = pd.DataFrame(rows)
        self.values.columns = ['Index', 'OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/IP', 'Search_Name']
        self.values.set_index('Index', inplace=True)
    
    def create_offensive_df(self, pos):
        rows = self.get_offensive_rows(pos)
        pos_val = pd.DataFrame(rows)
        pos_val.columns = ['Index', 'OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G']
        pos_val.set_index('Index', inplace=True)
        return pos_val
    
    def create_pitching_df(self, pos):
        rows = self.get_pitching_rows(pos)
        pos_val = pd.DataFrame(rows)
        pos_val.columns = ['Index', 'OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/IP']
        pos_val.set_index('Index', inplace=True)
        return pos_val
    
    def get_overall_value_rows(self):
        rows = []
        for pv in self.value_calculation.get_position_values(Position.OVERALL):
            row = []
            row.append(pv.player.index)
            row.append(pv.player.ottoneu_id)
            row.append(pv.value)
            row.append(pv.player.name)
            row.append(pv.player.team)
            row.append(pv.player.position)
            pp = self.value_calculation.projection.get_player_projection(pv.player.index)
            o_points = calculation_services.get_points(pp, Position.OFFENSE,self.league.format == ScoringFormat.SABR_POINTS)
            p_points = calculation_services.get_points(pp, Position.PITCHER,self.league.format == ScoringFormat.SABR_POINTS)
            row.append(o_points + p_points)
            # Currently have a 'PAR' column that might be defunct
            row.append("0")
            games = pp.get_stat(StatType.G_HIT)
            if games is None or games == 0:
                row.append(0)
            else:
                row.append(o_points / games)
            ip = pp.get_stat(StatType.IP)
            if ip is None or ip == 0:
                row.append(0)
            else:
                row.append(p_points/ip)
            row.append(util.string_util.normalize(pv.player.name))
            rows.append(row)
        return rows

    def get_offensive_rows(self, pos):
        rows = []
        for pv in self.value_calculation.get_position_values(pos):
            row = []
            row.append(pv.player.index)
            row.append(pv.player.ottoneu_id)
            row.append(pv.value)
            row.append(pv.player.name)
            row.append(pv.player.team)
            row.append(pv.player.position)
            pp = self.value_calculation.projection.get_player_projection(pv.player.index)
            o_points = calculation_services.get_points(pp, Position.OFFENSE,self.league.format == ScoringFormat.SABR_POINTS)
            row.append(o_points)
            # Currently have a 'PAR' column that might be defunct
            row.append("0")
            games = pp.get_stat(StatType.G_HIT)
            if games is None or games == 0:
                row.append(0)
            else:
                row.append(o_points / games)
            rows.append(row)
        return rows
    
    def get_pitching_rows(self, pos):
        rows = []
        for pv in self.value_calculation.get_position_values(pos):
            row = []
            row.append(pv.player.index)
            row.append(pv.player.ottoneu_id)
            row.append(pv.value)
            row.append(pv.player.name)
            row.append(pv.player.team)
            row.append(pv.player.position)
            pp = self.value_calculation.projection.get_player_projection(pv.player.index)
            p_points = calculation_services.get_points(pp, Position.PITCHER,self.league.format == ScoringFormat.SABR_POINTS)
            row.append(p_points)
            # Currently have a 'PAR' column that might be defunct
            row.append("0")
            ip = pp.get_stat(StatType.IP)
            if ip is None or ip == 0:
                row.append(0)
            else:
                row.append(p_points/ip)
            rows.append(row)
        return rows

    def initialize_draft_legacy(self):
        self.popup = tk.Toplevel()
        tk.Label(self.popup, text='Draft Initializing').grid(row=0,column=0)
        progress = 0
        self.progress_var = tk.DoubleVar()
        self.progress_var.set(0)
        ttk.Progressbar(self.popup, variable=self.progress_var, maximum=100).grid(row=1, column=0)
        self.popup.pack_slaves()

        self.progress_step = sv = tk.StringVar()
        self.progress_label = ttk.Label(self.popup, textvariable=self.progress_step)
        self.progress_label.grid(column=0,row=2)

        try:
            self.value_file_path = os.path.join(self.value_dir.get(), 'values.csv')

            if not os.path.exists(self.value_file_path):
                self.value_file_path = os.path.join(self.value_dir.get(), 'ottoneu_values.csv')
                if not os.path.exists(self.value_file_path):
                    mb.showinfo('Bad Directory', f'The directory {self.value_dir.get()} does not contain a values.csv or ottoneu_values.csv file. Please select a different directory.')
                    return
            self.progress_step.set('Getting Ottoneu Player Universe...')
            self.popup.update()
            scraper = Scrape_Ottoneu()
            self.positions = scraper.get_avg_salary_ds()
            progress += 30
            self.progress_var.set(progress)
            self.popup.update()

            self.progress_step.set('Loading Player Values...')
            try:
                result = self.load_values()
            except KeyError as ke:
                logging.exception('Error initializing draft')
                mb.showerror("Initialization Error", f"There was an error initializing the draft. Columns missing in one or more *values.csv files.")
                self.progress_var.set(100)
                self.popup.destroy()
                return
            except Exception as e:
                logging.exception('Error initializing draft')
                mb.showerror("Initialization Error", f"There was an error initializing the draft, see ./logs/draft.log")
                self.progress_var.set(100)
                self.popup.destroy()
                return

            if not result:
                mb.showinfo('Bad Player Ids', f'The player ids did not match Ottoneu or FanGraphs ids. Please use one of these player id types.')
                self.progress_var.set(100)
                self.popup.destroy()
                return

            self.controller.league.ottoneu_id = self.league_num_entry.get()
            self.progress_step.set(f'Getting League {self.controller.league.ottoneu_id} Rosters...')
            progress += 30
            self.progress_var.set(progress)
            self.popup.update()
            self.rosters = scraper.scrape_roster_export(self.controller.league.ottoneu_id)
            #Below used for api testing
            #self.rosters = pd.read_csv('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Test\\rosters.csv')
            #self.rosters.set_index("ottoneu ID", inplace=True)
            #self.rosters.index = self.rosters.index.astype(str, copy=False)

            progress += 15
            self.progress_var.set(progress)
            self.popup.update()
            self.progress_step.set('Updating Values With Roster Info...')
            self.update_rostered_players()
            if 'Blank col 0' in self.values.columns:
                self.values.sort_values(by=['Blank col 0'], ascending=[False], inplace=True)
                for pos in Position.get_offensive_pos():
                    self.pos_values[pos].sort_values(by=['P/G'], ascending=[False], inplace=True)
                for pos in Position.get_pitching_pos():
                    self.pos_values[pos].sort_values(by=['P/IP'], ascending=[False], inplace=True)
            
            self.progress_step.set('Initialization Complete')
            self.progress_var.set(100)
            self.setup_win.destroy()
        
        except Exception as e:
            logging.exception('Error initializing draft')
            mb.showerror("Initialization Error", f"There was an error initializing the draft, see ./logs/draft.log")
            self.popup.destroy()
            return
    
    def calc_inflation(self):
        num_teams = self.controller.league.num_teams
        pos_df = self.values.loc[self.values['Salary'] == 0]
        pos_val = pos_df.loc[~(pos_df['Value'] < 1)]
        remaining_valued_roster_spots = self.valued_roster_spots - len(self.rosters)
        self.remaining_value = pos_val['Value'].sum() - remaining_valued_roster_spots
        self.remaining_dollars = (num_teams*400 - self.extra_value) - self.rosters['Salary'].sum() - remaining_valued_roster_spots
        self.inflation = self.remaining_dollars / self.remaining_value
        self.inflation_str_var.set(f'Inflation: {"{:.1f}".format((self.inflation - 1.0)*100)}%')

    def update_rostered_players(self):
        self.values = self.values.merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna(0)
        for pos in self.pos_values:
            self.pos_values[pos] = self.pos_values[pos].merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna(0)
            #set index to str because if you managed to get them all as ints, you will not match up on the back side
            #self.pos_values[pos].index = self.pos_values[pos].index.astype(str, copy = False)

    def load_roster_salaries(self, salary_col):
        split = salary_col.split('$')
        if len(split) > 1:
            return int(split[1])
        else:
            return 0

    def convert_rates(self, value):
        if value == 'NA' or math.isnan(value):
            return float(0)
        elif type(value) == float:
            return value
        else:
            return float(value)

    def load_values(self):
        self.values = pd.read_csv(self.value_file_path, index_col=0)
        self.values.index = self.values.index.astype(str, copy = False)
        soto_id = self.values.index[self.values['Name'] == "Juan Soto"].tolist()[0]
        if soto_id == '23717':
            self.id_type = IdType.OTTONEU
        elif soto_id == '20123':
            self.id_type = IdType.FG
            self.values = self.values.astype({'OttoneuID': 'str'})
        else:
            return False
        #Leif output. Remap columns
        self.values.rename(columns={'price': 'Value', 'Pos':'Position(s)', 'FGPts':'Points', 'FGPtspIP':'P/IP', 'FGPtspG':'P/G', 'FGPts_G':'P/G', 'SABRPts' : 'Points', 'SABRPtspIP' : 'P/IP', 'SABRPtspG':'P/G'}, inplace=True)
        
        self.values['P/G'] = self.values['P/G'].apply(self.convert_rates)
        self.values['P/IP'] = self.values['P/IP'].apply(self.convert_rates)

        if not 'PAR' in self.values:
            self.values['PAR'] = 0
        
        if not 'Team' in self.values:
            self.values = self.values.merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
            self.values['Team'] = self.values['Org']
            self.values = self.values.drop('Org', axis=1)

        if self.id_type == IdType.OTTONEU:
            if self.values['Value'].dtype == object:
                self.values['Blank col 0'] = self.values['Value'].apply(lambda x: float(x.split('$')[1]))
            else:
                self.values['Blank col 0'] = self.values['Value']
            #Leif doesn't have teams, need to merge here
            self.values = self.values[['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/IP']]    
        else:
            self.values =  self.values[['OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/IP']]   

        if not self.values['Value'].dtype == object:
            self.values['Value'] = self.values['Value'].apply(lambda x: "${:.0f}".format(x)) 

        #TODO: data validation here
        self.pos_values = {}
        for pos in Position.get_offensive_pos():
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path, index_col=0)
                self.pos_values[pos] = self.pos_values[pos].astype({'OttoneuID': 'str'})
                if not 'PAR' in self.pos_values[pos]:
                        self.pos_values[pos]['PAR'] = 0
                if not 'Team' in self.pos_values[pos]:
                    self.pos_values[pos] = self.pos_values[pos].merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
                    self.pos_values[pos]['Team'] = self.pos_values[pos]['Org']
                    self.pos_values[pos] = self.pos_values[pos].drop('Org', axis=1)
                if self.id_type == IdType.OTTONEU:
                    self.pos_values[pos]['Blank col 0'] = 0
                    self.pos_values[pos] = self.pos_values[pos][['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G']]
                else:
                    self.pos_values[pos] =  self.pos_values[pos][['OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G']]
                #self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
            else:
                if pos == 'MI':
                    self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains("2B|SS", case=False, regex=True)].sort_values(by=['P/G'], ascending=[False])
                elif pos == 'Util':
                    self.pos_values[pos] = self.values.loc[self.values['P/G'] > 0].sort_values(by=['P/G'], ascending=[False])
                else:
                    self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains(pos)].sort_values(by=['P/G'], ascending=[False])
                self.pos_values[pos] = self.pos_values[pos].drop('P/IP', axis=1)
        for pos in Position.get_pitching_pos():
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path, index_col=0)
                self.pos_values[pos] = self.pos_values[pos].astype({'OttoneuID': 'str'})
                if not 'PAR' in self.pos_values[pos]:
                        self.pos_values[pos]['PAR'] = 0
                if not 'Team' in self.pos_values[pos]:
                    self.pos_values[pos] = self.pos_values[pos].merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
                    self.pos_values[pos]['Team'] = self.pos_values[pos]['Org']
                    self.pos_values[pos] = self.pos_values[pos].drop('Org', axis=1)
                if self.id_type == IdType.OTTONEU:
                    self.pos_values[pos]['Blank col 0'] = 0
                    self.pos_values[pos] = self.pos_values[pos][['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/IP']]
                else:
                    self.pos_values[pos] =  self.pos_values[pos][['OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/IP']]
                #self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
            else:
                self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains(pos)].sort_values(by=['P/IP'], ascending=[False])
                self.pos_values[pos] = self.pos_values[pos].drop('P/G', axis=1)
        
        self.values['Search_Name'] = self.values['Name'].apply(lambda x: util.string_util.normalize(x))

        return True
    
    def league_change(self):
        while self.controller.league is None:
            self.controller.select_league()
        if self.controller.league is not None and self.league != self.controller.league:
            self.league = self.controller.league
            self.league_text_var.set(f'League {self.controller.league.name} Draft')
            self.draft = draft_services.get_draft_by_league(self.controller.league.index)
            self.initialize_draft(same_values=True)

    
    def value_change(self):
        if self.controller.value_calculation is not None and self.value_calculation != self.controller.value_calculation:
            self.value_calculation = self.controller.value_calculation
            self.initialize_draft()

def main():
    try:
        run_event = threading.Event()
        tool = DraftTool(run_event)
    except Exception:
        if run_event.is_set:
            run_event.clear()
    finally:
        if run_event.is_set:
            run_event.clear()

if __name__ == '__main__':
    main()
