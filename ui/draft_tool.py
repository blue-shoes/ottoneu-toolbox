import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
import tkinter.messagebox as mb
from tkinter.messagebox import OK
import os
import os.path
import pandas as pd
import numpy as np
import util.string_util
import queue
import logging
import threading
from time import sleep
from datetime import datetime, timedelta

from functools import partial

from scrape.scrape_ottoneu import Scrape_Ottoneu 
from domain.enum import Position, ScoringFormat, StatType, Preference as Pref, AvgSalaryFom, RankingBasis, ProjectionType
from ui.table.table import Table, sort_cmp, ScrollableTreeFrame
from ui.dialog import progress, draft_target, cm_team_assignment
from ui.dialog.wizard import couchmanagers_import
from ui.tool.tooltip import CreateToolTip
from ui.view.standings import Standings
from services import salary_services, league_services, calculation_services, player_services, draft_services
from demo import draft_demo

player_cols = ('Name','Value','Inf. Cost','Pos','Team')
hit_5x5_cols = ('R', 'HR', 'RBI', 'SB', 'AVG')
pitch_5x5_cols = ('W', 'SV', 'K', 'ERA', 'WHIP')
hit_4x4_cols = ('R', 'HR', 'OBP', 'SLG')
pitch_4x4_cols = ('K', 'HR/9', 'ERA', 'WHIP')

class DraftTool(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.demo_source = controller.demo_source
        self.demo_thread = None
        self.run_event = controller.run_event
        self.run_event.set()
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
        self.cm_text = StringVar()
        self.cm_text.set('Link CouchManagers')
        self.start_draft_sv = StringVar()
        self.start_draft_sv.set('Start Draft Monitor')
        self.stop_draft_sv = StringVar()
        self.stop_draft_sv.set('Stop Draft Monitor')

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
        self.values_name.set(f'Selected Values: {self.value_calculation.name}')

        self.salary_information_refresh()

        self.draft = draft_services.get_draft_by_league(self.controller.league.index)

        self.initialize_draft(same_values)

        #Clean up previous demo run
        if os.path.exists(draft_demo.demo_trans):
            os.remove(draft_demo.demo_trans)

        return True

    def leave_page(self):
        return True
    
    def salary_information_refresh(self):
        pd = progress.ProgressDialog(self.parent, title='Downloading latest salary information...')
        pd.increment_completion_percent(10)

        format_salary_refresh = salary_services.get_last_refresh(self.controller.league.format)
        if format_salary_refresh is None or (datetime.now() - format_salary_refresh.last_refresh) > timedelta(days=1):
            salary_services.update_salary_info(format=self.league.format)
            self.controller.value_calculation = calculation_services.load_calculation(self.controller.value_calculation.index)
            self.value_calculation = self.controller.value_calculation
        pd.complete()

    def calculate_extra_value(self):
        captured_value = 0
        self.valued_roster_spots = 0
        for pv in self.value_calculation.get_position_values(Position.OVERALL):
            if pv.value < 1:
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
        running_list_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky='nsew')
        running_list_frame.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.tab_control = ttk.Notebook(running_list_frame, width=570)
        self.tab_control.grid(row=0, column=0, sticky='ns')

        self.create_search()

        #TODO: Clean this up
        self.standings = Standings(self)
        self.standings.grid(row=1,column=2, sticky='nsew')

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
        cols = ('Name','Value','Inf. Cost','Pos','Team','Points', 'SABR Pts', 'P/G','HP/G','P/PA','P/IP','SABR PIP','PP/G','SABR PPG', 'Avg. Price', 'L10 Price', 'Roster %')
        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W
        custom_sort = {}
        custom_sort['Value'] = partial(self.default_value_sort, Position.OVERALL)
        self.overall_view = ov = ScrollableTreeFrame(overall_frame, cols,sortable_columns=cols, column_widths=widths, init_sort_col='Value', column_alignments=align, custom_sort=custom_sort, pack=False)
        ov.table.set_row_select_method(self.on_select)
        ov.table.set_right_click_method(self.player_rclick)
        self.set_row_colors(ov.table)
        ov.pack(fill='both', expand=True)
        ov.table.set_refresh_method(self.refresh_overall_view)

        for pos in (Position.get_offensive_pos() + Position.get_pitching_pos()):
            pos_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(pos_frame, text=pos.value) 
            if pos in Position.get_offensive_pos():
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G', 'P/PA','Avg. Price', 'L10 Price', 'Roster %', 'R', 'HR', 'RBI', 'AVG', 'SB', 'OBP', 'SLG')
            else:
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','SABR Pts','P/IP','SABR PIP','PP/G','SABR PPG', 'Avg. Price', 'L10 Price', 'Roster %', 'K', 'ERA', 'WHIP', 'W', 'SV', 'HR/9')
            custom_sort = {}
            custom_sort['Value'] = partial(self.default_value_sort, pos)
            self.pos_view[pos] = pv = ScrollableTreeFrame(pos_frame, cols,sortable_columns=cols, column_widths=widths, column_alignments=align, init_sort_col='Value', custom_sort=custom_sort, pack=False)
            pv.pack(fill='both', expand=True)
            pv.table.set_row_select_method(self.on_select)
            pv.table.set_right_click_method(self.player_rclick)
            self.set_row_colors(pv.table)
            pv.table.set_refresh_method(lambda _pos = pos: self.refresh_pos_table(_pos))
        
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

        self.target_table = tt = ScrollableTreeFrame(target_frame, columns=cols, column_alignments=align, 
            column_widths=widths, sortable_columns=cols, reverse_col_sort=rev_sort, init_sort_col='Value', pack=False)
        tt.pack(fill='both', expand=True)
        tt.table.set_row_select_method(self.on_select)
        tt.table.set_right_click_method(self.target_rclick)
        self.set_row_colors(tt.table, targets=False)
        tt.table.set_refresh_method(self.refresh_targets)
    
    def create_search(self):
        self.values_name = StringVar()
        if self.controller.preferences.getboolean('Draft', Pref.DOCK_DRAFT_PLAYER_SEARCH, fallback=False):
            monitor_frame = ttk.Frame(self)
            monitor_frame.grid(row=1, column=0, columnspan=2)
            self.start_monitor = ttk.Button(monitor_frame, textvariable=self.start_draft_sv, command=self.start_draft_monitor)
            self.start_monitor.grid(column=0,row=0)
            CreateToolTip(self.start_monitor, 'Begin watching league for new draft results')
            self.monitor_status = tk.StringVar()
            self.monitor_status.set('Not started')
            self.monitor_status_lbl = tk.Label(monitor_frame, textvariable=self.monitor_status, fg='red')
            self.monitor_status_lbl.grid(column=2,row=0)
            self.stop_monitor = ttk.Button(monitor_frame, textvariable=self.stop_draft_sv, command=self.stop_draft_monitor)
            self.stop_monitor.grid(column=1,row=0)
            self.stop_monitor['state'] = DISABLED
            CreateToolTip(self.stop_monitor, 'Stop watching league for new draft results')
            self.link_cm_btn = btn = ttk.Button(monitor_frame, textvariable=self.cm_text, command=self.link_couchmanagers)
            btn.grid(column=2, row=0)
            CreateToolTip(btn, 'Link a CouchManagers draft to this league.')

            self.inflation_str_var = tk.StringVar()

            self.inflation_lbl = ttk.Label(monitor_frame, textvariable=self.inflation_str_var)
            self.inflation_lbl.grid(column=3,row=0)

            search_frame = ttk.Frame(self.tab_control, border=4)
            self.tab_control.add(search_frame, text='Search')

            entry_frame = ttk.Frame(search_frame)
            entry_frame.pack(side=TOP, fill='x', expand=False)
            ttk.Label(entry_frame, text='Search:').pack(side=LEFT)

            self.search_string = ss = tk.StringVar()
            ss.trace("w", lambda name, index, mode, sv=ss: self.search_view.table.refresh())
            ttk.Entry(entry_frame, textvariable=ss).pack(side=LEFT, fill='x', expand=True)

            f = ttk.Frame(search_frame, border=4)
            f.pack(side=TOP, fill='both', expand=True)

            self.create_search_table(f, 0, 0)

            search_unrostered_btn = ttk.Checkbutton(entry_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv, command=self.search_view.table.refresh)
            search_unrostered_btn.pack(side=LEFT, fill='none', expand=False, padx=5)
            search_unrostered_btn.state(['!alternate'])
            CreateToolTip(search_unrostered_btn, 'Include 0% rostered players in the search results')
        
        else:

            search_frame = ttk.Frame(self)
            search_frame.grid(column=0,row=1, padx=5, sticky=tk.NW, pady=17)
            ttk.Label(search_frame, text = 'Player Search: ', font='bold').grid(column=0,row=1,pady=5)

            self.search_string = ss = tk.StringVar()
            ss.trace("w", lambda name, index, mode, sv=ss: self.search_view.table.refresh())
            ttk.Entry(search_frame, textvariable=ss).grid(column=1,row=1)

            self.start_monitor = ttk.Button(search_frame, textvariable=self.start_draft_sv, command=self.start_draft_monitor)
            self.start_monitor.grid(column=0,row=3)
            CreateToolTip(self.start_monitor, 'Begin watching league for new draft results')
            self.monitor_status = tk.StringVar()
            self.monitor_status.set('Monitor not started')
            self.monitor_status_lbl = tk.Label(search_frame, textvariable=self.monitor_status, fg='red')
            self.monitor_status_lbl.grid(column=1,row=3)
            self.stop_monitor = ttk.Button(search_frame, textvariable=self.stop_draft_sv, command=self.stop_draft_monitor)
            self.stop_monitor.grid(column=0,row=4)
            CreateToolTip(self.stop_monitor, 'Stop watching league for new draft results')
            self.stop_monitor['state'] = DISABLED
            self.link_cm_btn = btn = ttk.Button(search_frame, textvariable=self.cm_text, command=self.link_couchmanagers)
            btn.grid(column=0, row=5)
            CreateToolTip(btn, 'Link a CouchManagers draft to this league.')

            self.inflation_str_var = tk.StringVar()

            self.inflation_lbl = ttk.Label(search_frame, textvariable=self.inflation_str_var)
            self.inflation_lbl.grid(column=0,row=6)

            if self.value_calculation is None:
                self.values_name.set('No value calculation selected')
            else:
                self.values_name.set(f'Selected Values: {self.value_calculation.name}')
            ttk.Label(search_frame, textvariable=self.values_name).grid(row=7, column=0, sticky=tk.NW)

            f = ttk.Frame(self, width=250)
            f.grid(column=1,row=1, sticky='nsew')
            self.columnconfigure(1, weight=1)
            
            ttk.Label(f, text = 'Search Results', font='bold').pack(expand=False, fill='x', side=TOP)

            self.create_search_table(f, col=0, row=1)

            search_unrostered_btn = ttk.Checkbutton(search_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv, command=self.search_view.table.refresh)
            search_unrostered_btn.grid(row=2, column=1, sticky=tk.NW, pady=5)
            search_unrostered_btn.state(['!alternate'])
            CreateToolTip(search_unrostered_btn, 'Include 0% rostered players in the search results')
    
    def create_search_table(self, parent, col, row, col_span=1):
        cols = ('Name','Value','Salary','Inf. Cost','Pos','Team','Points','SABR Pts', 'P/G','HP/G','P/PA','P/IP', 'SABR PIP','PP/G', 'SABR PPG', 'Roster %')
        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W
        custom_sort = {}
        custom_sort['Value'] = self.default_search_sort
        self.search_view = sv = ScrollableTreeFrame(parent, columns=cols, column_alignments=align, column_widths=widths, sortable_columns=cols, init_sort_col='Value', custom_sort=custom_sort, pack=False)      
        sv.pack(fill='both', expand=True, side=TOP)
        sv.table.set_row_select_method(self.on_select)
        sv.table.set_right_click_method(self.player_rclick)
        self.set_row_colors(sv.table)
        sv.table.set_refresh_method(self.update_player_search)

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
                target = draft_services.create_target(self.draft.index, playerid, dialog.price)
                self.draft.targets.append(target)
        else: 
            dialog = draft_target.Dialog(self, playerid, target.price)
            if dialog.status == OK:
                draft_services.update_target(target, dialog.price)
                self.draft.set_target(playerid, dialog.price)
        if dialog.status == OK:
            self.refresh_planning_frame()
            self.set_player_tags_all_tables(playerid)
    
    def remove_target(self, playerid):
        target = self.draft.get_target_by_player(playerid)
        self.draft.targets.remove(target)
        draft_services.delete_target(target.index)
        self.refresh_planning_frame()
        self.set_player_tags_all_tables(playerid)
    
    def remove_player(self, playerid):
        self.removed_players.append(playerid)
        self.refresh_views()
    
    def restore_player(self, playerid):
        self.removed_players.remove(playerid)
        self.refresh_views()
    
    def set_player_tags_all_tables(self, player_id):
        tags = self.get_row_tags(player_id)
        self.overall_view.table.set_tags_by_row_text(player_id, tags)
        for pos in self.pos_view:
            self.pos_view[pos].table.set_tags_by_row_text(player_id, tags)
        self.search_view.table.set_tags_by_row_text(player_id, tags)

    def on_select(self, event):
        if len(event.widget.selection()) == 1:
            print(f'Selection is {int(event.widget.item(event.widget.selection()[0])["text"])}')
    

    def default_value_sort(self, pos:Position):
        if pos == Position.OVERALL:
            pos_table = self.overall_view.table
        else:
            pos_table = self.pos_view.get(pos).table
        if self.league.format is None:
            l = [(self.set(k, 'Values'), k) for k in self.get_children('')]
            sorted(l, reverse=self.table.reverse_sort['Values'], key=lambda x: sort_cmp(x)) 
        if self.value_calculation.projection is None:
            col2 = 'Roster %'
        else:
            if ScoringFormat.is_points_type(self.league.format):
                #if pos == Position.OVERALL:
                    if ScoringFormat.is_sabr(self.league.format):
                        col2 = 'SABR Pts'
                    else:
                        col2 = 'Points'
            else:
                if pos == Position.OVERALL:
                    col2 = 'Roster %'
                elif pos in Position.get_offensive_pos():
                    col2 = 'R'
                else:
                    #TODO: I'd like this to be WHIP, but need to make it not reverse sort then
                    col2 = 'K'
        l = [((pos_table.set(k, 'Value'), pos_table.set(k,col2)), k) for k in pos_table.get_children('')]
        l = sorted(l, reverse=pos_table.reverse_sort['Value'], key=lambda x: self.sort_dual_columns(x))
        return l

    def default_search_sort(self):
        l = [((self.search_view.table.set(k, 'Value'), self.search_view.table.set(k,'Roster %')), k) for k in self.search_view.table.get_children('')]
        l = sorted(l, reverse=self.search_view.table.reverse_sort['Value'], key=lambda x: self.sort_dual_columns(x))
        return l
    
    def sort_dual_columns(self, cols):
        primary = float(cols[0][0][1:])
        val = cols[0][1][:-1]
        if val is None or val == '':
            secondary = 0
        else:
            secondary = float(val)
        return (primary, secondary)

    def start_draft_monitor(self):
        if self.draft.cm_draft is None:
            self.monitor_status.set('Draft Started')
            self.monitor_status_lbl.config(fg='green')
            self.start_monitor['state'] = DISABLED
            self.link_cm_btn['state'] = DISABLED
            if self.run_event.is_set():
                self.run_event.clear()
                logging.info('---Starting Draft Monitor---')
                self.monitor_thread = threading.Thread(target = self.refresh_thread)
                self.monitor_thread.daemon = True
                self.monitor_thread.start()
                
                self.parent.update_idletasks()
                self.parent.after(1000, self.update_ui)

            if self.demo_source:
                self.demo_thread = threading.Thread(target=draft_demo.demo_draft, args=(self.league, self.run_event))
                self.demo_thread.daemon = True
                self.demo_thread.start()
        else:
            if self.draft.cm_draft.setup:
                self.resolve_cm_draft_with_rosters(init=False)
            else:
                self.check_new_cm_teams()
    
    def update(self):
        league_services.calculate_league_table(self.league, self.value_calculation, fill_pt=(self.standings.standings_type.get() == 1), inflation=self.inflation)
        self.standings.refresh_standings()

    def update_ui(self):
        if self.run_event.is_set() and self.queue.empty():
            self.stop_monitor['state'] = DISABLED
            return
        try:
            if str(self.stop_monitor['state']) == DISABLED:
                self.stop_monitor['state'] = ACTIVE
            if not self.queue.empty():
                key, data = self.queue.get()
                logging.debug(f'Updating the following positions: {data}')
                self.refresh_views(data)
        except Exception as Argument:
            logging.exception('Exception updating Draft Tool UI.')
        finally:
            self.parent.after(1000, self.update_ui)
    
    def stop_draft_monitor(self):
        if self.draft.cm_draft is None:
            logging.info('!!!Stopping Draft Monitor!!!')
            self.run_event.set()
            self.start_monitor['state'] = ACTIVE
            self.link_cm_btn['state'] = ACTIVE
            self.monitor_status.set('Draft stopped')
            self.monitor_status_lbl.config(fg='red')
            self.parent.update_idletasks()
        else:
            self.unlink_couchmanagers()
    
    def link_couchmanagers(self):
        if self.draft.cm_draft is not None:
            if not self.unlink_couchmanagers():
                return
        dialog = couchmanagers_import.Dialog(self.master, self.draft)
        if dialog.draft is not None and dialog.draft.cm_draft is not None:
            self.draft = dialog.draft
            if self.draft.cm_draft.setup:
                self.monitor_status.set(f'Using CM Draft {self.draft.cm_draft.cm_draft_id}')
                self.monitor_status_lbl.config(fg='green')
            else:
                self.monitor_status.set(f'Using CM Draft {self.draft.cm_draft.cm_draft_id} (not full)')
                self.monitor_status_lbl.config(fg='red')
            self.start_draft_sv.set('Refresh CM Draft')
            CreateToolTip(self.start_monitor, 'Gets the latest CouchManager draft results and applies them.')
            self.stop_draft_sv.set('Unlink CM Draft')
            self.stop_monitor['state'] = ACTIVE
            CreateToolTip(self.stop_monitor, 'Removes the connection to the CouchManagers draft for the league and reverts to the Ottoneu-only rosters.')
            if self.draft.cm_draft.setup:
                self.resolve_cm_draft_with_rosters(init=False)
            else:
                self.check_new_cm_teams()

    def unlink_couchmanagers(self):
        if mb.askyesno('Link New CouchManagers?', 'This will delete the current CouchManagers information for this draft. Continue?'):
            setup = self.draft.cm_draft.setup
            draft_services.delete_couchmanagers_draft(self.draft.cm_draft)
            self.draft.cm_draft = None
            if setup:
                self.initialize_draft(same_values=True)
            self.monitor_status.set('Not started')
            self.monitor_status_lbl.config(fg='red')
            self.start_draft_sv.set('Start Draft Monitor')
            CreateToolTip(self.start_monitor, 'Begin watching league for new draft results')
            self.stop_draft_sv.set('Stop Draft Monitor')
            self.stop_monitor['state'] = DISABLED
            CreateToolTip(self.stop_monitor, 'Stop watching league for new draft results')
            return True
        return False
    
    def check_new_cm_teams(self):
        prog = progress.ProgressDialog(self, 'Getting CM Draft Info...')
        prog.set_completion_percent(33)
        cm_teams = draft_services.get_couchmanagers_teams(self.draft.cm_draft.cm_draft_id)
        new_teams = []
        new_claims = False
        for team in cm_teams:
            found = False
            for team2 in self.draft.cm_draft.teams:
                if team[0] == team2.cm_team_id:
                    found = True
                    break
            if not found:
                if team[1] != '':
                    new_claims = True
                new_teams.append(team)
        prog.complete()
        if new_claims:
            dialog = cm_team_assignment.Dialog(self, self.draft, new_teams)
            if dialog.status == OK:
                self.draft = dialog.draft
                if self.draft.cm_draft.setup:
                    self.resolve_cm_draft_with_rosters()
                    self.monitor_status.set(f'Using CM Draft {self.draft.cm_draft.cm_draft_id}')
                    self.monitor_status_lbl.config(fg='green')
                
    def resolve_cm_draft_with_rosters(self, init:bool=True):
        prog = progress.ProgressDialog(self.parent, 'Updating Slow Draft Results...')
        prog.set_task_title('Getting CouchManagers Results...')
        prog.increment_completion_percent(15)
        cm_rosters_df = draft_services.get_couchmanagers_draft_dataframe(self.draft.cm_draft.cm_draft_id)
        if len(cm_rosters_df) == 0:
            #No results yet
            prog.complete()
            return
        prog.set_task_title('Resolving rosters...')
        prog.increment_completion_percent(50)
        pos_val = self.values.loc[~(self.values['Value'] < 1)]
        rows = []
        for idx, cm_player in cm_rosters_df.iterrows():
            if cm_player['ottid'] == 0:
                self.extra_value = self.extra_value - cm_player['Amount']
                continue
            found = False
            if cm_player['ottid'] in set(self.rosters['ottoneu ID']):
                continue
            if not found:
                row = []
                player = player_services.get_player_by_ottoneu_id(cm_player['ottid'])
                row.append(player.index)
                row.append(self.draft.cm_draft.get_toolbox_team_index_by_cm_team_id(cm_player['Team Number']))
                row.append(cm_player['ottid'])
                salary = cm_player['Amount']
                row.append(salary)
                rows.append(row)
                if not init:
                    if player.index in self.values.index:
                        self.values.at[player.index, 'Salary'] = salary
                        pos = player_services.get_player_positions(player)
                        for p in pos:                                    
                            self.pos_values[p].at[player.index, 'Salary'] = salary
                    if player.index not in pos_val.index:
                        self.extra_value = self.extra_value - salary
        if rows is None or len(rows) == 0:
            prog.complete()
            return
        df = pd.DataFrame(rows)
        df.columns = ['index', 'TeamID', 'ottoneu ID', 'Salary']
        df.set_index('index', inplace=True)
        self.rosters = pd.concat([self.rosters, df])
        if not init:
            self.refresh_views()
        prog.complete()
    
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
        logging.info('Entering Draft Refresh Loop')
        self.run_event.clear()
        while(not self.run_event.is_set()):
            try:
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
                    update_pos = set()
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
                            for p in pos:
                                if p in Position.get_pitching_pos():
                                    #Because of how we treat pitching, update all pitcher tables if it's a pitcher
                                    for p2 in Position.get_pitching_pos():
                                        update_pos.add(p2)
                                else:
                                    update_pos.add(p)
                            if last_trans.iloc[index]['Type'].upper() == 'ADD':
                                salary = int(last_trans.iloc[index]['Salary'].split('$')[1])
                                self.values.at[player.index, 'Salary'] = salary
                                self.update_remaining_extra_value(self.values.at[player.index, 'Value'], salary)
                                for p in pos:  
                                    if p in Position.get_pitching_pos():
                                        #Because of how we treat pitching, update all pitcher tables if it's a pitcher
                                        for p2 in Position.get_pitching_pos():              
                                            self.pos_values[p2].at[player.index, 'Salary'] = salary          
                                    else:          
                                        self.pos_values[p].at[player.index, 'Salary'] = salary
                            elif 'CUT' in last_trans.iloc[index]['Type'].upper():
                                self.revert_extra_value(self.values.at[player.index, 'Value'], self.values.at[player.index, 'Salary'])
                                self.values.at[player.index, 'Salary'] = 0
                                self.rosters.drop(player.index)
                                for p in pos:
                                    if p in Position.get_pitching_pos():
                                        #Because of how we treat pitching, update all pitcher tables if it's a pitcher
                                        for p2 in Position.get_pitching_pos():              
                                            self.pos_values[p2].at[player.index, 'Salary'] = 0
                                    else:
                                        self.pos_values[p].at[player.index, 'Salary'] = 0
                        index -= 1
                    last_time = most_recent
                    self.queue.put(('pos', list(update_pos)))
                    self.calc_inflation()
                    league_services.calculate_league_table(self.league, self.value_calculation, self.standings.standings_type.get() == 1, self.inflation)
            except Exception as Argument:
                logging.exception('Exception processing transaction.')
            finally:
                self.run_event.wait(delay)
        logging.info('Exiting Draft Refresh Loop')

    def refresh_views(self, pos_keys=None):
        self.inflation_str_var.set(f'Inflation: {"{:.1f}".format((self.inflation - 1.0)*100)}%')
        self.overall_view.table.refresh()
        if pos_keys == None:
            for pos in (Position.get_offensive_pos() + Position.get_pitching_pos()):
                self.pos_view[pos].table.refresh()
        else:
            for pos in pos_keys:
                logging.debug(f'updating {pos.value}')
                self.pos_view[pos].table.refresh()
        
        self.search_view.table.refresh()
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
            val = pos_df.iat[i, 1]
            value = '$' + "{:.0f}".format(val)
            if val < 1:
                inf_cost = f'${val}'
            else:
                inf_cost = '$' + "{:.0f}".format((val-1) * self.inflation + 1)
            position = pos_df.iat[i, 4]
            team = pos_df.iat[i, 3]
            pts = "{:.1f}".format(pos_df.iat[i, 5])
            sabr_pts = "{:.1f}".format(pos_df.iat[i, 6])
            ppg = "{:.2f}".format(pos_df.iat[i, 8])
            hppg = "{:.2f}".format(pos_df.iat[i, 9])
            pppa = "{:.2f}".format(pos_df.iat[i, 10])
            pip = "{:.2f}".format(pos_df.iat[i, 11])
            spip = "{:.2f}".format(pos_df.iat[i, 12])
            pppg = "{:.2f}".format(pos_df.iat[i, 13])
            spppg = "{:.2f}".format(pos_df.iat[i, 14])
            sal_tup = self.get_salary_tuple(int(id))
            tags = self.get_row_tags(id)
            self.overall_view.table.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, sabr_pts, ppg, hppg, pppa, pip, spip, pppg, spppg, sal_tup[0], sal_tup[1], sal_tup[2]), tags=tags)

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
            val = pos_df.iat[i, 1]
            value = '$' + "{:.0f}".format(val)
            if val < 1:
                inf_cost = f'${val}'
            else:
                inf_cost = '$' + "{:.0f}".format((val-1) * self.inflation + 1)
            position = pos_df.iat[i, 4]
            team = pos_df.iat[i, 3]
            pts = "{:.1f}".format(pos_df.iat[i, 5])
            sal_tup = self.get_salary_tuple(int(id))
            tags = self.get_row_tags(id)
            if pos in Position.get_offensive_pos():
                rate1 = "{:.2f}".format(pos_df.iat[i, 7])
                rate2 = "{:.2f}".format(pos_df.iat[i, 8])
                runs = "{:.0f}".format(pos_df.iat[i, 9])
                hr = "{:.0f}".format(pos_df.iat[i, 10])
                rbi = "{:.0f}".format(pos_df.iat[i, 11])
                avg = "{:.3f}".format(pos_df.iat[i, 12])
                sb = "{:.0f}".format(pos_df.iat[i, 13])
                obp = "{:.3f}".format(pos_df.iat[i, 14])
                slg = "{:.3f}".format(pos_df.iat[i, 15])
                self.pos_view[pos].table.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, rate1, rate2, sal_tup[0], sal_tup[1], sal_tup[2], runs, hr, rbi, avg, sb, obp, slg), tags=tags)
            else:
                sabr_pts = "{:.1f}".format(pos_df.iat[i, 6])
                rate1 = "{:.2f}".format(pos_df.iat[i, 8])
                rate2 = "{:.2f}".format(pos_df.iat[i, 9])
                rate3 = "{:.2f}".format(pos_df.iat[i, 10])
                rate4 = "{:.2f}".format(pos_df.iat[i, 11])
                k = "{:.0f}".format(pos_df.iat[i, 12])
                era = "{:.3f}".format(pos_df.iat[i, 13])
                whip = "{:.3f}".format(pos_df.iat[i, 14])
                w = "{:.0f}".format(pos_df.iat[i, 15])
                sv = "{:.0f}".format(pos_df.iat[i, 16])
                hr_per_9 = "{:.2f}".format(pos_df.iat[i, 17])
                self.pos_view[pos].table.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts,sabr_pts, rate1, rate2, rate3, rate4, sal_tup[0], sal_tup[1], sal_tup[2], k, era, whip, w, sv, hr_per_9), tags=tags)
    def get_salary_tuple(self, playerid):
        si = self.value_calculation.get_player_value(playerid, pos=Position.OVERALL).player.get_salary_info_for_format(self.league.format)
        if si is None:
            avg = '$0.0'
            l10 = '$0.0'
            roster = '0.0%'
        else:
            if self.controller.preferences.get('General', Pref.AVG_SALARY_FOM, fallback=AvgSalaryFom.MEAN.value) == AvgSalaryFom.MEAN.value:
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
    
    def set_row_colors(self, table: Table, targets=True):
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
            if (si is None or si.roster_percentage == 0) and not self.search_unrostered_bv.get():
                continue
            id = player.index
            name = player.name
            pos = player.position
            team = player.team
            if id in self.values.index:
                val = self.value_calculation.get_player_value(id, Position.OVERALL).value
                value = '$' + "{:.0f}".format(val)
                if val < 1:
                    inf_cost = f'${val}'
                else:
                    inf_cost = '$' + "{:.0f}".format((val-1) * self.inflation + 1)
            else:
                value = '$0'
                inf_cost = '$0'
            if id in self.rosters.index:
                salary = f"${int(self.rosters.at[id, 'Salary'])}"
            else:
                salary = '$0'
            if self.value_calculation.projection is not None:
                pp = self.value_calculation.projection.get_player_projection(id)
                if pp is not None and self.value_calculation.projection.valid_points:
                    if self.value_calculation.projection.type == ProjectionType.VALUE_DERIVED:
                        pts = pp.get_stat(StatType.POINTS)
                        spts = pp.get_stat(StatType.POINTS)
                        ppg = pp.get_stat(StatType.PPG)
                        hppg = ppg
                        pppa = '0.00'
                        pip = pp.get_stat(StatType.PIP)
                        spip = pp.get_stat(StatType.PIP)
                        pppg = '0.00'
                        spppg = '0.00'
                    else:
                        h_pts = calculation_services.get_points(pp, Position.OFFENSE)
                        p_pts = calculation_services.get_points(pp, Position.PITCHER, False)
                        s_p_pts = calculation_services.get_points(pp, Position.PITCHER, True)
                        pts = "{:.1f}".format(h_pts + p_pts)
                        spts = "{:.1f}".format(h_pts + s_p_pts)
                        h_g = pp.get_stat(StatType.G_HIT)
                        h_pa = pp.get_stat(StatType.PA)
                        if h_g is None or h_g == 0 or h_pa is None or h_pa == 0:
                            ppg = '0.00'
                            hppg = '0.00'
                            pppa = '0.00'
                        else:
                            ppg = "{:.2f}".format(h_pts/h_g)
                            hppg = ppg
                            pppa = "{:.2f}".format(h_pts/h_pa)
                        p_ip = pp.get_stat(StatType.IP)
                        p_g = pp.get_stat(StatType.G_PIT)
                        if p_ip is None or p_ip == 0 or p_g is None or p_g == 0:
                            pip = '0.00'
                            spip = pip
                            pppg = pip
                            spppg = pip
                        else:
                            pip = "{:.2f}".format(p_pts / p_ip)
                            spip = "{:.2f}".format(s_p_pts / p_ip)
                            pppg = "{:.2f}".format(p_pts / p_g)
                            spppg = "{:.2f}".format(s_p_pts / p_g)
                else:
                    pts = '0.0'
                    spts = '0.0'
                    ppg = '0.00'
                    hppg = '0.00'
                    pppa = '0.00'
                    pip = '0.00'
                    spip = '0.00'
                    pppg = '0.00'
                    spppg = '0.00'
            else:
                pts = '0.0'
                spts = '0.0'
                ppg = '0.00'
                hppg = '0.00'
                pppa = '0.00'
                pip = '0.00'
                spip = '0.00'
                pppg = '0.00'
                spppg = '0.00'
            
            if si is None:
                roster_percent = '0.0%'
            else:
                roster_percent = "{:.1f}".format(si.roster_percentage) + "%"

            tags = self.get_row_tags(id)
            self.search_view.table.insert('', tk.END, text=str(id), tags=tags, values=(name, value, salary, inf_cost,pos, team, pts, spts, ppg, hppg, pppa, pip, spip, pppg, spppg, roster_percent))
   
    def refresh_planning_frame(self):
        self.target_table.table.refresh()

    def refresh_targets(self):
        for target in self.draft.targets:
            id = target.player_id
            name = target.player.name
            t_price = f'${target.price}'
            pv = self.value_calculation.get_player_value(id, pos=Position.OVERALL)
            if pv is None:
                value = '$0'
            else:
                value = '$' + "{:.0f}".format(pv.value)
            pos = target.player.position
            tags = self.get_row_tags(id)
            self.target_table.table.insert('', tk.END, text=id, tags=tags, values=(name, t_price, value, pos))
        
    def initialize_draft(self, same_values=False): 
        self.calculate_extra_value() 
        restart = False
        if not self.run_event.is_set():
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

        if self.draft.cm_draft is not None:
            self.monitor_status.set(f'Using CM Draft {self.draft.cm_draft.cm_draft_id}')
            self.monitor_status_lbl.config(fg='green')
            self.start_draft_sv.set('Refresh CM Draft')
            CreateToolTip(self.start_monitor, 'Gets the latest CouchManager draft results and applies them.')
            self.stop_draft_sv.set('Unlink CM Draft')
            self.stop_monitor['state'] = ACTIVE
            CreateToolTip(self.stop_monitor, 'Removes the connection to the CouchManagers draft for the league and reverts to the Ottoneu-only rosters.')
            if self.draft.cm_draft.setup:
                self.resolve_cm_draft_with_rosters()
            else:
                self.check_new_cm_teams()
                
        pd.set_task_title('Updating available players...')
        self.update_rostered_players()
        pd.increment_completion_percent(5)

        self.calc_inflation()

        pd.set_task_title('Refreshing views...')
        self.set_visible_columns()

        self.standings.league = self.controller.league
        self.standings.value_calc = self.controller.value_calculation
        league_services.calculate_league_table(self.league, self.value_calculation, self.standings.standings_type.get() == 1, self.inflation)
        self.standings.standings_table.table.refresh()

        self.refresh_views()
        pd.complete()
        if restart:
            self.start_draft_monitor()
    
    def calc_format_matches_league(self) -> bool:
        if ScoringFormat.is_points_type(self.league.format):
            return ScoringFormat.is_points_type(self.value_calculation.format)
        return self.league.format == self.value_calculation.format

    def set_visible_columns(self) -> None:
        salary_cols = ('Avg. Price', 'L10 Price', 'Roster %')
        stock_overall = player_cols + salary_cols
        stock_search = ('Name','Value','Inf. Cost','Salary','Pos','Team')
        if self.value_calculation.projection is None or not self.calc_format_matches_league():
            self.overall_view.table.set_display_columns(stock_overall)
            for pos in self.pos_view:
                self.pos_view[pos].table.set_display_columns(stock_overall)
            self.search_view.table.set_display_columns(stock_search + ('Roster %',))
        elif ScoringFormat.is_points_type(self.league.format):
            sabr = ScoringFormat.is_sabr(self.league.format)
            if sabr:
                p_points = ('SABR Pts',)
            else:
                p_points = ('Points',)
            if self.value_calculation.hitter_basis == RankingBasis.PPG:
                if self.value_calculation.pitcher_basis == RankingBasis.PPG:
                    hit_rate = ('HP/G',)
                else:
                    hit_rate = ('P/G',)
                pos_hit_rate = ('P/G',)
            elif self.value_calculation.hitter_basis == RankingBasis.PPPA:
                hit_rate = ('P/PA',)
                pos_hit_rate = hit_rate
            elif self.value_calculation.hitter_basis == RankingBasis.FG_AC:
                hit_rate = pos_hit_rate = tuple()
            else:
                raise Exception(f"Unhandled hitter_basis {self.value_calculation.hitter_basis}")
            if self.value_calculation.pitcher_basis == RankingBasis.PIP:
                if sabr:
                    pitch_rate = ('SABR PIP',)
                else:
                    pitch_rate = ('P/IP',)
            elif self.value_calculation.pitcher_basis == RankingBasis.PPG:
                if sabr:
                    pitch_rate = ('SABR PPG',)
                else:
                    pitch_rate = ('PP/G',)
            elif self.value_calculation.pitcher_basis == RankingBasis.FG_AC:
                pitch_rate = tuple()
            else:
                raise Exception(f"Unhandled pitcher_basis {self.value_calculation.pitcher_basis}")
            self.overall_view.table.set_display_columns(player_cols + p_points + hit_rate + pitch_rate + salary_cols)
            for pos in self.pos_view:
                if pos in Position.get_offensive_pos():
                    self.pos_view[pos].table.set_display_columns(player_cols + ('Points',) + pos_hit_rate + salary_cols)
                else:
                    self.pos_view[pos].table.set_display_columns(player_cols + p_points + pitch_rate + salary_cols)
            self.search_view.table.set_display_columns(stock_search + p_points + hit_rate + pitch_rate + ('Roster %',))
        elif self.league.format == ScoringFormat.OLD_SCHOOL_5X5:
            self.overall_view.table.set_display_columns(stock_overall)
            for pos in self.pos_view:
                if pos in Position.get_offensive_pos():
                    self.pos_view[pos].table.set_display_columns(player_cols + hit_5x5_cols + salary_cols)
                else:
                    self.pos_view[pos].table.set_display_columns(player_cols + pitch_5x5_cols + salary_cols)
            self.search_view.table.set_display_columns(stock_search + ('Roster %',))
        elif self.league.format == ScoringFormat.CLASSIC_4X4:
            self.overall_view.table.set_display_columns(stock_overall)
            for pos in self.pos_view:
                if pos in Position.get_offensive_pos():
                    self.pos_view[pos].table.set_display_columns(player_cols + hit_4x4_cols + salary_cols)
                else:
                    self.pos_view[pos].table.set_display_columns(player_cols + pitch_4x4_cols + salary_cols)
            self.search_view.table.set_display_columns(stock_search + ('Roster %',))
        else:
            raise Exception(f"Unknown league type {self.league.format}")
    
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
        self.values.columns = ['Index', 'OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'SABR Pts','PAR', 'P/G', 'HP/G', 'P/PA', 'P/IP', 'SABR PIP', 'PP/G', 'SABR PPG', 'Search_Name']
        self.values.set_index('Index', inplace=True)
    
    def create_offensive_df(self, pos):
        rows = self.get_offensive_rows(pos)
        pos_val = pd.DataFrame(rows)
        pos_val.columns = ['Index', 'OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/PA', 'R', 'HR', 'RBI', 'AVG', 'SB', 'OBP', 'SLG']
        pos_val.set_index('Index', inplace=True)
        return pos_val
    
    def create_pitching_df(self, pos):
        rows = self.get_pitching_rows(pos)
        pos_val = pd.DataFrame(rows)
        pos_val.columns = ['Index', 'OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'SABR Pts', 'PAR', 'P/IP', 'SABR PIP', 'PP/G', 'SABR PPG', 'K', 'ERA', 'WHIP', 'W', 'SV', 'HR/9']
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
            if self.value_calculation.projection is not None:
                pp = self.value_calculation.projection.get_player_projection(pv.player.index)
                if pp is None or not self.value_calculation.projection.valid_points:
                    row.append(0.00) #points
                    row.append(0.00) #spoints
                    row.append(0.00) #par
                    row.append(0.00) #hit rate
                    row.append(0.00) #hit rate hp/g
                    row.append(0.00) #hit rate p/pa
                    row.append(0.00) #pitch rate p/ip
                    row.append(0.00) #pitch rate sabr p/ip
                    row.append(0.00) #pitch rate p/g
                    row.append(0.00) #pitch rate sabr p/g
                else:
                    if self.value_calculation.projection.type == ProjectionType.VALUE_DERIVED:
                        row.append(pp.get_stat(StatType.POINTS))
                        row.append(pp.get_stat(StatType.POINTS))
                        row.append(0)
                        row.append(pp.get_stat(StatType.PPG))
                        row.append(pp.get_stat(StatType.PPG))
                        row.append(0)
                        row.append(pp.get_stat(StatType.PIP))
                        row.append(pp.get_stat(StatType.PIP))
                        row.append(0)
                        row.append(0)
                    else:
                        o_points = calculation_services.get_points(pp, Position.OFFENSE)
                        p_points = calculation_services.get_points(pp, Position.PITCHER,False)
                        s_p_points = calculation_services.get_points(pp, Position.PITCHER,True)
                        row.append(o_points + p_points)
                        row.append(o_points + s_p_points)
                        # Currently have a 'PAR' column that might be defunct
                        row.append("0")
                        games = pp.get_stat(StatType.G_HIT)
                        pa = pp.get_stat(StatType.PA)
                        if games is None or games == 0 or pa is None or pa == 0:
                            row.append(0)
                            row.append(0)
                            row.append(0)
                        else:
                            row.append(o_points / games)
                            row.append(o_points/games)
                            row.append(o_points / pa)
                        ip = pp.get_stat(StatType.IP)
                        games = pp.get_stat(StatType.G_PIT)
                        if ip is None or ip == 0 or games is None or games == 0:
                            row.append(0)
                            row.append(0)
                            row.append(0)
                            row.append(0)
                        else:
                            row.append(p_points/ip)
                            row.append(s_p_points/ip)
                            row.append(p_points/games)
                            row.append(s_p_points/games)
            else:
                row.append(0.00) #points
                row.append(0.00) #sabr points
                row.append(0.00) #par
                row.append(0.00) #hit rate p/g
                row.append(0.00) #hit rate hp/g
                row.append(0.00) #hit rate p/pa
                row.append(0.00) #pitch rate p/ip
                row.append(0.00) #pitch rate sabr p/ip
                row.append(0.00) #pitch rate pp/g
                row.append(0.00) #pitch rate sabr pp/g
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
            if self.value_calculation.projection is not None:
                pp = self.value_calculation.projection.get_player_projection(pv.player.index)
                if pp is not None:
                    if self.value_calculation.projection.valid_points:
                        if self.value_calculation.projection.type == ProjectionType.VALUE_DERIVED:
                            row.append(pp.get_stat(StatType.POINTS))
                            row.append(0)
                            row.append(pp.get_stat(StatType.PPG))
                            row.append(0)
                        else:
                            o_points = calculation_services.get_points(pp, Position.OFFENSE,self.league.format == ScoringFormat.SABR_POINTS)
                            row.append(o_points)
                            # Currently have a 'PAR' column that might be defunct
                            row.append("0")
                            games = pp.get_stat(StatType.G_HIT)
                            pa = pp.get_stat(StatType.PA)
                            if games is None or games == 0 or pa is None or pa == 0:
                                row.append(0)
                                row.append(0)
                            else:
                                row.append(o_points / games)
                                row.append(o_points / pa)
                    else:
                        row.append(0.00) # points
                        row.append(0.00) # par
                        row.append(0.00) # hit rate ppg
                        row.append(0.00) # hit rate pppa
                    r_and_hr = FALSE
                    if self.value_calculation.projection.valid_5x5:
                        r_and_hr = True
                        row.append(pp.get_stat(StatType.R))
                        row.append(pp.get_stat(StatType.HR))
                        row.append(pp.get_stat(StatType.RBI))
                        row.append(pp.get_stat(StatType.AVG))
                        row.append(pp.get_stat(StatType.SB))

                    if self.value_calculation.projection.valid_4x4:
                        if not r_and_hr:
                            r_and_hr = True
                            row.append(pp.get_stat(StatType.R))
                            row.append(pp.get_stat(StatType.HR))
                            row.append(0)
                            row.append(0)
                            row.append(0)
                        row.append(pp.get_stat(StatType.OBP))
                        row.append(pp.get_stat(StatType.SLG))
                    elif r_and_hr:
                        row.append(0) # OBP
                        row.append(0) # SLG
                    else:
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                    
                else:
                    row.append(0.00) # points
                    row.append(0.00) # par
                    row.append(0.00) # hit rate ppg
                    row.append(0.00) # hit rate pppa

                    row.append(0) # Runs
                    row.append(0) # HR
                    row.append(0) # RBI
                    row.append(0) # AVG
                    row.append(0) # SB
                    row.append(0) # OBP
                    row.append(0) # SLG
            else:
                row.append(0.00) # points
                row.append(0.00) # par
                row.append(0.00) # hit rate ppg
                row.append(0.00) # hit rate pppa

                row.append(0) # Runs
                row.append(0) # HR
                row.append(0) # RBI
                row.append(0) # AVG
                row.append(0) # SB
                row.append(0) # OBP
                row.append(0) # SLG
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
            if self.value_calculation.projection is not None:
                pp = self.value_calculation.projection.get_player_projection(pv.player.index)
                if pp is not None:
                    if self.value_calculation.projection.valid_points:
                        if self.value_calculation.projection.type == ProjectionType.VALUE_DERIVED:
                            row.append(pp.get_stat(StatType.POINTS))
                            row.append(pp.get_stat(StatType.POINTS))
                            row.append(0)
                            row.append(pp.get_stat(StatType.PIP))
                            row.append(pp.get_stat(StatType.PIP))
                            row.append(0)
                            row.append(0)
                        else:
                            p_points = calculation_services.get_points(pp, Position.PITCHER,True)
                            s_p_points = calculation_services.get_points(pp, Position.PITCHER,False)
                            row.append(p_points)
                            row.append(s_p_points)
                            # Currently have a 'PAR' column that might be defunct
                            row.append("0")
                            ip = pp.get_stat(StatType.IP)
                            games = pp.get_stat(StatType.G_PIT)
                            if ip is None or ip == 0 or games is None or games == 0:
                                row.append(0)
                                row.append(0)
                                row.append(0)
                                row.append(0)
                            else:
                                row.append(p_points/ip)
                                row.append(s_p_points/ip)
                                row.append(p_points/games)
                                row.append(s_p_points/games)
                    else:
                        row.append(0.00) # points
                        row.append(0.00) # points
                        row.append(0.00) # par
                        row.append(0.00) # pitch rate pip
                        row.append(0.00) # pitch rate sabr pip
                        row.append(0.00) # pitch rate ppg
                        row.append(0.00) # pitch rate sabr ppg
                    k_era_whip = False
                    if self.value_calculation.projection.valid_5x5:
                        k_era_whip = True
                        row.append(pp.get_stat(StatType.SO))
                        row.append(pp.get_stat(StatType.ERA))
                        row.append(pp.get_stat(StatType.WHIP))
                        row.append(pp.get_stat(StatType.W))
                        row.append(pp.get_stat(StatType.SV))
                    if self.value_calculation.projection.valid_4x4:
                        if not k_era_whip:
                            row.append(pp.get_stat(StatType.SO))
                            row.append(pp.get_stat(StatType.ERA))
                            row.append(pp.get_stat(StatType.WHIP))
                            row.append(0)
                            row.append(0)
                        row.append(pp.get_stat(StatType.HR_PER_9))
                    elif k_era_whip:
                        row.append(0)
                    else:
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                        row.append(0)
                else:
                    row.append(0.00) # points
                    row.append(0) # sabr points
                    row.append(0.00) # par
                    row.append(0.00) # pitch rate pip
                    row.append(0.00) # pitch rate sabr pip
                    row.append(0.00) # pitch rate ppg
                    row.append(0.00) # pitch rate sabr ppg
                    row.append(0)
                    row.append(0)
                    row.append(0)
                    row.append(0)
                    row.append(0)
                    row.append(0)
            else:
                row.append(0.00) # points
                row.append(0.00) # sabr points
                row.append(0.00) # par
                row.append(0.00) # pitch rate pip
                row.append(0.00) # pitch rate sabr pip
                row.append(0.00) # pitch rate ppg
                row.append(0.00) # pitch rate sabr ppg
                row.append(0)
                row.append(0)
                row.append(0)
                row.append(0)
                row.append(0)
                row.append(0)
            rows.append(row)
        return rows

    def calc_inflation(self):
        num_teams = self.controller.league.num_teams
        pos_df = self.values.loc[self.values['Salary'] == 0]
        pos_val = pos_df.loc[~(pos_df['Value'] < 1)]
        remaining_valued_roster_spots = len(pos_val)
        self.remaining_value = pos_val['Value'].sum() - remaining_valued_roster_spots
        self.remaining_dollars = (num_teams*400 - self.extra_value) - self.rosters['Salary'].sum() - remaining_valued_roster_spots
        self.inflation = self.remaining_dollars / self.remaining_value  

    def update_rostered_players(self):
        self.values = self.values.merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna(0)
        for idx, row in self.values.iterrows():
            self.update_remaining_extra_value(row['Value'], row['Salary'])
        for pos in self.pos_values:
            self.pos_values[pos] = self.pos_values[pos].merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna(0)
    
    def update_remaining_extra_value(self, value:float, salary:float) -> None:
        if salary > 0:
            if value <= 0:
                self.extra_value = self.extra_value - salary
            elif value < 10 and value < salary:
                subtract = (salary - value) / (2*value)
                self.extra_value = self.extra_value - subtract
    
    def revert_extra_value(self, value:float, old_salary:float) -> None:
        if value <= 0:
            self.extra_value = self.extra_value + old_salary
        elif value < 10 and value < old_salary:
            readd = (old_salary - value) / (2*value)
            self.extra_value = self.extra_value + readd

    def league_change(self):
        while self.controller.league is None:
            self.controller.select_league()
        if self.controller.league is not None and self.league != self.controller.league:
            self.league = self.controller.league
            self.league_text_var.set(f'League {self.controller.league.name} Draft')
            self.draft = draft_services.get_draft_by_league(self.controller.league.index)
            self.salary_information_refresh()
            self.initialize_draft(same_values=True)
    
    def value_change(self):
        if self.controller.value_calculation is not None and self.value_calculation != self.controller.value_calculation:
            self.value_calculation = self.controller.value_calculation
            self.values_name.set(f'Selected Values: {self.value_calculation.name}')
            self.initialize_draft()

def main():
    try:
        run_event = threading.Event()
        tool = DraftTool(run_event)
    except Exception:
        if not run_event.is_set():
            run_event.set()
    finally:
        if not run_event.is_set():
            run_event.set()

if __name__ == '__main__':
    main()
