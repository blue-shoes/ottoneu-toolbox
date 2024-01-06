import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
import tkinter.messagebox as mb
from tkinter.messagebox import OK
import os
import queue
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List
from requests.exceptions import HTTPError

from functools import partial

from ui.app_controller import Controller
from ui.toolbox_view import ToolboxView
from domain.domain import League, Player, ValueCalculation, PlayerValue, Roster_Spot
from domain.enum import Position, ScoringFormat, StatType, Preference as Pref, AvgSalaryFom, RankingBasis, ProjectionType, InflationMethod, CalculationDataType, Platform
from ui.table.table import Table, sort_cmp, ScrollableTreeFrame
from ui.dialog import progress, draft_target, cm_team_assignment
from ui.dialog.wizard import couchmanagers_import
from ui.tool.tooltip import CreateToolTip
from ui.view.standings import Standings
from services import salary_services, league_services, calculation_services, player_services, draft_services, custom_scoring_services, yahoo_services, ottoneu_services, starting_positions_services
from demo import draft_demo
from util import string_util

player_cols = ('Name','Value','Inf. Cost','Rank','Round','Pos','Team')
player_salary_cap_columns = ('Name','Value','Inf. Cost','Pos','Team')
player_no_salary_cap_columns =('Name','Rank','Round','Pos','Team')
hit_5x5_cols = ('R', 'HR', 'RBI', 'SB', 'AVG')
pitch_5x5_cols = ('W', 'SV', 'K', 'ERA', 'WHIP')
hit_4x4_cols = ('R', 'HR', 'OBP', 'SLG')
pitch_4x4_cols = ('K', 'HR/9', 'ERA', 'WHIP')
all_hitting_stats = tuple([st.display for st in StatType.get_all_hit_stattype()])
all_pitching_stats = tuple([st.display for st in StatType.get_all_pitch_stattype()])

class DraftTool(ToolboxView):

    league:League
    value_calculation:ValueCalculation
    pos_view:Dict[Position, ScrollableTreeFrame]
    run_event:threading.Event
    rostered_ids:List[int]
    rostered_detached_id_map:Dict[ScrollableTreeFrame, List[str]]
    removed_detached_id_map:Dict[ScrollableTreeFrame, List[str]]
    player_to_round_map:Dict[int, int]

    def __init__(self, parent:tk.Frame, controller:Controller):
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
        self.removed_players = []
        self.rostered_ids = []
        self.league = None
        self.value_calculation = None
        self.starting_set = starting_positions_services.get_ottoneu_position_set()
        self.cm_text = StringVar()
        self.cm_text.set('Link CouchManagers')
        self.start_draft_sv = StringVar()
        self.start_draft_sv.set('Start Draft Monitor')
        self.stop_draft_sv = StringVar()
        self.stop_draft_sv.set('Stop Draft Monitor')
        self.inflation_method = self.controller.preferences.get('General', Pref.INFLATION_METHOD, fallback=InflationMethod.ROSTER_SPOTS_ONLY.value)
        self.rostered_detached_id_map = {}
        self.removed_detached_id_map = {}
        self.player_to_round_map = {}

        self.__create_main()
    
    def on_show(self):
        if self.controller.league is None or not league_services.league_exists(self.controller.league):
            self.controller.select_league(yahoo_refresh=False)
        if self.controller.value_calculation is None or len(self.controller.value_calculation.values) == 0:
            self.controller.select_value_set()
        if self.controller.league is None or self.controller.value_calculation is None:
            return False

        self.league = self.controller.league
        self.value_calculation = self.controller.value_calculation

        self.starting_set = self.value_calculation.starting_set

        self.league_text_var.set(f'{self.controller.league.name} Draft')
        self.values_name.set(f'Selected Values: {self.value_calculation.name}')

        if self.league.platform == Platform.OTTONEU:
            self.salary_information_refresh()

        self.draft = draft_services.get_draft_by_league(self.controller.league.index)

        self.__initialize_draft()

        #Clean up previous demo run
        if os.path.exists(draft_demo.demo_trans):
            os.remove(draft_demo.demo_trans)
        if os.path.exists(draft_demo.yahoo_demo_trans):
            os.remove(draft_demo.yahoo_demo_trans)

        return True

    def leave_page(self):
        self.run_event.set()
        if self.league.platform == Platform.YAHOO:
            self.controller.league = league_services.get_league(self.league.index)
        return True
    
    def salary_information_refresh(self):
        pd = progress.ProgressDialog(self.parent, title='Downloading latest salary information...')
        pd.increment_completion_percent(10)

        format_salary_refresh = salary_services.get_last_refresh(self.controller.league.format)
        if format_salary_refresh is None or (datetime.now() - format_salary_refresh.last_refresh) > timedelta(days=1):
            salary_services.update_salary_info(format=self.league.format)
        pd.complete()

    def __create_main(self):
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

        self.__create_search()

        self.standings = Standings(self)
        self.standings.grid(row=1,column=2, sticky='nsew')

        button_frame = ttk.Frame(running_list_frame)
        button_frame.grid(row=0, column=1, sticky=tk.N, pady=15)

        show_drafted_btn = ttk.Checkbutton(button_frame, text="Show rostered players?", variable=self.show_drafted_players, command=self.__toggle_show_drafted)
        show_drafted_btn.grid(row=0, column=1, sticky=tk.NW, pady=5)
        show_drafted_btn.state(['!alternate'])

        show_removed_btn = ttk.Checkbutton(button_frame, text="Show removed players?", variable=self.show_removed_players, command=self.__toggle_show_removed)
        show_removed_btn.grid(row=1, column=1, sticky=tk.NW)
        show_removed_btn.state(['!alternate'])

        self.pos_view = {}

        overall_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(overall_frame, text='Overall')
        cols = ('Name','Value','Inf. Cost','Rank','Round','Pos','Team','Points', 'SABR Pts', 'P/G','HP/G','P/PA','P/IP','SABR PIP','PP/G','SABR PPG', 'Avg. Price', 'L10 Price', 'Roster %')
        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W
        custom_sort = {}
        custom_sort['Value'] = partial(self.__default_value_sort, Position.OVERALL)
        self.overall_view = ov = ScrollableTreeFrame(overall_frame, cols,sortable_columns=cols, column_widths=widths, init_sort_col='Value', column_alignments=align, custom_sort=custom_sort, pack=False)
        ov.table.set_row_select_method(self.__on_select)
        ov.table.set_right_click_method(self.__player_rclick)
        self.__set_row_colors(ov.table)
        ov.pack(fill='both', expand=True)
        ov.table.set_refresh_method(self.__refresh_overall_view)

        self.__create_position_tables(init=True)
        
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
        tt.table.set_row_select_method(self.__on_select)
        tt.table.set_right_click_method(self.__target_rclick)
        self.__set_row_colors(tt.table, targets=False)
        tt.table.set_refresh_method(self.__refresh_targets)
    
    def __create_position_tables(self, init:bool=False) -> None:

        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W

        positions:List[Position] = []
        if init:
            positions.append(Position.OFFENSE)
            positions.append(Position.PITCHER)
        

        positions.extend(Position.get_ordered_list([p.position for p in self.starting_set.positions]))

        for pos in positions:
            pos_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(pos_frame, text=pos.value) 
            if pos.offense:
                cols = ('Name','Value','Inf. Cost','Rank','Round','Pos','Team','Points','P/G', 'P/PA','Avg. Price', 'L10 Price', 'Roster %') + tuple([st.display for st in StatType.get_all_hit_stattype()])
            else:
                cols = ('Name','Value','Inf. Cost','Rank','Round','Pos','Team','Points','SABR Pts','P/IP','SABR PIP','PP/G','SABR PPG', 'Avg. Price', 'L10 Price', 'Roster %') + tuple([st.display for st in StatType.get_all_pitch_stattype()])
            custom_sort = {}
            custom_sort['Value'] = partial(self.__default_value_sort, pos)
            self.pos_view[pos] = pv = ScrollableTreeFrame(pos_frame, cols,sortable_columns=cols, column_widths=widths, column_alignments=align, init_sort_col='Value', custom_sort=custom_sort, pack=False)
            pv.pack(fill='both', expand=True)
            pv.table.set_row_select_method(self.__on_select)
            pv.table.set_right_click_method(self.__player_rclick)
            self.__set_row_colors(pv.table)
            pv.table.set_refresh_method(lambda _pos = pos: self.__refresh_pos_table(_pos))

    def __create_search(self):
        self.values_name = StringVar()
        if self.controller.preferences.getboolean('Draft', Pref.DOCK_DRAFT_PLAYER_SEARCH, fallback=False):
            monitor_frame = ttk.Frame(self)
            monitor_frame.grid(row=1, column=0, columnspan=2)
            self.start_monitor = ttk.Button(monitor_frame, textvariable=self.start_draft_sv, command=self.__start_draft_monitor)
            self.start_monitor.grid(column=0,row=0)
            CreateToolTip(self.start_monitor, 'Begin watching league for new draft results')
            self.monitor_status = tk.StringVar()
            self.monitor_status.set('Not started')
            self.monitor_status_lbl = tk.Label(monitor_frame, textvariable=self.monitor_status, fg='red')
            self.monitor_status_lbl.grid(column=2,row=0)
            self.stop_monitor = ttk.Button(monitor_frame, textvariable=self.stop_draft_sv, command=self.__stop_draft_monitor)
            self.stop_monitor.grid(column=1,row=0)
            self.stop_monitor['state'] = DISABLED
            CreateToolTip(self.stop_monitor, 'Stop watching league for new draft results')
            self.link_cm_btn = btn = ttk.Button(monitor_frame, textvariable=self.cm_text, command=self.__link_couchmanagers)
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
            ss.trace_add("write", lambda name, index, mode, sv=ss: self.search_view.table.refresh())
            ttk.Entry(entry_frame, textvariable=ss).pack(side=LEFT, fill='x', expand=True)

            f = ttk.Frame(search_frame, border=4)
            f.pack(side=TOP, fill='both', expand=True)

            self.__create_search_table(f, 0, 0)

            search_unrostered_btn = ttk.Checkbutton(entry_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv, command=self.search_view.table.refresh)
            search_unrostered_btn.pack(side=LEFT, fill='none', expand=False, padx=5)
            search_unrostered_btn.state(['!alternate'])
            CreateToolTip(search_unrostered_btn, 'Include 0% rostered players in the search results')
        
        else:
            search_frame = ttk.Frame(self)
            search_frame.grid(column=0,row=1, padx=5, sticky=tk.NW, pady=17)
            ttk.Label(search_frame, text = 'Player Search: ', font='bold').grid(column=0,row=1,pady=5)

            self.search_string = ss = tk.StringVar()
            ss.trace_add("write", lambda name, index, mode, sv=ss: self.search_view.table.refresh())
            ttk.Entry(search_frame, textvariable=ss).grid(column=1,row=1)

            self.start_monitor = ttk.Button(search_frame, textvariable=self.start_draft_sv, command=self.__start_draft_monitor)
            self.start_monitor.grid(column=0,row=3)
            CreateToolTip(self.start_monitor, 'Begin watching league for new draft results')
            self.monitor_status = tk.StringVar()
            self.monitor_status.set('Monitor not started')
            self.monitor_status_lbl = tk.Label(search_frame, textvariable=self.monitor_status, fg='red')
            self.monitor_status_lbl.grid(column=1,row=3)
            self.stop_monitor = ttk.Button(search_frame, textvariable=self.stop_draft_sv, command=self.__stop_draft_monitor)
            self.stop_monitor.grid(column=0,row=4)
            CreateToolTip(self.stop_monitor, 'Stop watching league for new draft results')
            self.stop_monitor['state'] = DISABLED
            self.link_cm_btn = btn = ttk.Button(search_frame, textvariable=self.cm_text, command=self.__link_couchmanagers)
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

            self.__create_search_table(f, col=0, row=1)

            search_unrostered_btn = ttk.Checkbutton(search_frame, text="Search 0% Rostered?", variable=self.search_unrostered_bv, command=self.search_view.table.refresh)
            search_unrostered_btn.grid(row=2, column=1, sticky=tk.NW, pady=5)
            search_unrostered_btn.state(['!alternate'])
            CreateToolTip(search_unrostered_btn, 'Include 0% rostered players in the search results')
    
    def __create_search_table(self, parent, col, row, col_span=1):
        cols = ('Name','Value','Salary','Inf. Cost','Rank','Round','Pos','Team','Points','SABR Pts', 'P/G','HP/G','P/PA','P/IP', 'SABR PIP','PP/G', 'SABR PPG', 'Roster %')
        widths = {}
        widths['Name'] = 125
        widths['Pos'] = 75
        align = {}
        align['Name'] = W
        custom_sort = {}
        custom_sort['Value'] = self.__default_search_sort
        self.search_view = sv = ScrollableTreeFrame(parent, columns=cols, column_alignments=align, column_widths=widths, sortable_columns=cols, init_sort_col='Value', custom_sort=custom_sort, pack=False)      
        sv.pack(fill='both', expand=True, side=TOP)
        sv.table.set_row_select_method(self.__on_select)
        sv.table.set_right_click_method(self.__player_rclick)
        self.__set_row_colors(sv.table)
        sv.table.set_refresh_method(self.__update_player_search)

    def __target_rclick(self, event):
        playerid = int(event.widget.identify_row(event.y))
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Change Target Price", command=lambda: self.__target_player(playerid))
        popup.add_command(label="Remove Target", command=lambda: self.__remove_target(playerid))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def __player_rclick(self, event):
        playerid = int(event.widget.identify_row(event.y))
        popup = tk.Menu(self.parent, tearoff=0)
        popup.add_command(label="Target Player", command=lambda: self.__target_player(int(playerid)))
        popup.add_separator()
        if playerid in self.removed_players:
            popup.add_command(label='Restore Player', command=lambda: self.__restore_player(int(playerid)))
        else:
            popup.add_command(label='Remove Player', command=lambda: self.__remove_player(int(playerid)))
        try:
            popup.post(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def __target_player(self, playerid):
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
            self.__refresh_planning_frame()
            self.__set_player_tags_all_tables(playerid)
    
    def __remove_target(self, playerid):
        target = self.draft.get_target_by_player(playerid)
        self.draft.targets.remove(target)
        draft_services.delete_target(target.index)
        self.__refresh_planning_frame()
        self.__set_player_tags_all_tables(playerid)
    
    def __remove_player(self, playerid):
        self.removed_players.append(playerid)
        self.__set_player_tags_all_tables(playerid)
        if not self.show_removed_players.get():
            str_pid = str(playerid)
            for view, row_list in self.removed_detached_id_map.items():
                if str_pid in view.table.get_children():
                    row_list.append(str_pid)
                    view.table.detach(str_pid)
    
    def __restore_player(self, playerid):
        self.removed_players.remove(playerid)
        if not self.show_removed_players.get():
            str_pid = str(playerid)
            for view, row_list in self.removed_detached_id_map.items():
                if str_pid in row_list:
                    row_list.remove(str_pid)
                    view.table.reattach(str_pid, '', tk.END)
                    view.table.resort()
        self.__set_player_tags_all_tables(playerid)
    
    def __set_player_tags_all_tables(self, player_id):
        tags = self.__get_row_tags(player_id)
        pid_str = str(player_id)
        if pid_str in self.overall_view.table.get_children():
            self.overall_view.table.item(pid_str, tags=tags)
        for _, view in self.pos_view.items():
            if pid_str in view.table.get_children():
                view.table.item(pid_str, tags=tags)
        if pid_str in self.search_view.table.get_children():
            self.search_view.table.item(pid_str, tags=tags)

    def __on_select(self, event:Event):
        if len(event.widget.selection()) == 1:
            print(f'Selection is {int(event.widget.selection()[0])}')

    def __default_value_sort(self, pos:Position):
        if pos == Position.OVERALL:
            pos_table = self.overall_view.table
        else:
            pos_table = self.pos_view.get(pos).table
        if self.league.format is None or not self.league.platform == Platform.OTTONEU:
            l = [(pos_table.set(k, 'Value'), k) for k in pos_table.get_children('')]
            l = sorted(l, reverse=pos_table.reverse_sort['Value'], key=lambda x: sort_cmp(x)) 
            return l
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
                elif pos.offense:
                    col2 = 'R'
                else:
                    #TODO: I'd like this to be WHIP, but need to make it not reverse sort then
                    col2 = 'K'
        l = [((pos_table.set(k, 'Value'), pos_table.set(k,col2)), k) for k in pos_table.get_children('')]
        l = sorted(l, reverse=pos_table.reverse_sort['Value'], key=lambda x: self.__sort_dual_columns(x))
        return l

    def __default_search_sort(self):
        l = [((self.search_view.table.set(k, 'Value'), self.search_view.table.set(k,'Roster %')), k) for k in self.search_view.table.get_children('')]
        l = sorted(l, reverse=self.search_view.table.reverse_sort['Value'], key=lambda x: self.__sort_dual_columns(x))
        return l
    
    def __sort_dual_columns(self, cols):
        primary = float(cols[0][0][1:])
        val = cols[0][1][:-1]
        if val is None or val == '':
            secondary = 0
        else:
            try:
                secondary = float(val)
            except ValueError:
                secondary = 0
        return (primary, secondary)

    def __start_draft_monitor(self):
        if self.draft.cm_draft is None:
            self.monitor_status.set('Draft Started')
            self.monitor_status_lbl.config(fg='green')
            self.start_monitor['state'] = DISABLED
            self.link_cm_btn['state'] = DISABLED
            if self.run_event.is_set():
                self.run_event.clear()
                logging.info('---Starting Draft Monitor---')
                self.monitor_thread = threading.Thread(target = self.__refresh_thread)
                self.monitor_thread.daemon = True
                self.monitor_thread.start()
                
                self.parent.update_idletasks()
                self.parent.after(1000, self.__update_ui)

            if self.demo_source:
                self.demo_thread = threading.Thread(target=draft_demo.demo_draft, args=(self.league, self.run_event))
                self.demo_thread.daemon = True
                self.demo_thread.start()
        else:
            if self.draft.cm_draft.setup:
                self.__resolve_cm_draft_with_rosters(init=False)
            else:
                self.__check_new_cm_teams()
    
    def update(self):
        league_services.calculate_league_table(self.league, self.value_calculation, fill_pt=False, inflation=self.inflation)
        self.standings.refresh()

    def __update_ui(self):
        if self.run_event.is_set() and self.queue.empty():
            self.stop_monitor['state'] = DISABLED
            return
        try:
            if str(self.stop_monitor['state']) == DISABLED:
                self.stop_monitor['state'] = ACTIVE
            if not self.queue.empty():
                _, data = self.queue.get()
                self.__refresh_views(data[0], data[1])
        except Exception as Argument:
            logging.exception('Exception updating Draft Tool UI.')
        finally:
            self.parent.after(1000, self.__update_ui)
    
    def __stop_draft_monitor(self):
        if self.draft.cm_draft is None:
            logging.info('!!!Stopping Draft Monitor!!!')
            self.run_event.set()
            self.start_monitor['state'] = ACTIVE
            self.link_cm_btn['state'] = ACTIVE
            self.monitor_status.set('Draft stopped')
            self.monitor_status_lbl.config(fg='red')
            self.parent.update_idletasks()
        else:
            self.__unlink_couchmanagers()
    
    def __link_couchmanagers(self):
        if self.draft.cm_draft is not None:
            if not self.__unlink_couchmanagers():
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
                self.__resolve_cm_draft_with_rosters(init=False)
            else:
                self.__check_new_cm_teams()

    def __unlink_couchmanagers(self):
        if mb.askyesno('Link New CouchManagers?', 'This will delete the current CouchManagers information for this draft. Continue?'):
            setup = self.draft.cm_draft.setup
            draft_services.delete_couchmanagers_draft(self.draft.cm_draft)
            self.draft.cm_draft = None
            if setup:
                self.__initialize_draft(same_values=True)
            self.monitor_status.set('Not started')
            self.monitor_status_lbl.config(fg='red')
            self.start_draft_sv.set('Start Draft Monitor')
            CreateToolTip(self.start_monitor, 'Begin watching league for new draft results')
            self.stop_draft_sv.set('Stop Draft Monitor')
            self.stop_monitor['state'] = DISABLED
            CreateToolTip(self.stop_monitor, 'Stop watching league for new draft results')
            return True
        return False
    
    def __check_new_cm_teams(self):
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
                    self.__resolve_cm_draft_with_rosters()
                    self.monitor_status.set(f'Using CM Draft {self.draft.cm_draft.cm_draft_id}')
                    self.monitor_status_lbl.config(fg='green')
                
    def __resolve_cm_draft_with_rosters(self, init:bool=True) -> List[Player]:
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
        drafted = []
        for _, cm_player in cm_rosters_df.iterrows():
            if self.league.is_rostered_by_ottoneu_id(cm_player['ottid']):
                continue
            salary = string_util.parse_dollar(cm_player['Amount'])
            player = player_services.get_player_by_ottoneu_id(cm_player['ottid'])
            team_id = self.draft.cm_draft.get_toolbox_team_index_by_cm_team_id(cm_player['Team Number'])
            self.__add_trans_to_rosters(player, salary, team_id)
            drafted.append(player)

        if len(drafted) == 0:
            prog.complete()
            return
        if not init:
            self.__refresh_views(drafted=drafted)
        prog.complete()
        return drafted
    
    def __add_trans_to_rosters(self, player:Player, salary:int, team_id:int, add_player:bool=True):
        self.rostered_ids.append(player.index)
        for team in self.league.teams:
            if team.site_id == team_id:
                rs = Roster_Spot()
                rs.player = player
                rs.player_id = player.index
                rs.salary = salary
                team.roster_spots.append(rs)
                break
        pv = self.value_calculation.get_player_value(player.index, Position.OVERALL)
        if pv is not None and pv.value > 0:
            val = pv.value
        else:
            val = 0
        if self.league.is_linked():
            self.inflation = league_services.update_league_inflation_last_trans(self.league, val, salary=salary, inf_method=self.inflation_method, add_player=add_player)

    def __refresh_thread(self):
        last_time = datetime.now() - timedelta(minutes=30)
        if self.league.platform == Platform.OTTONEU:
            delay = 45
        elif self.league.platform == Platform.YAHOO:
            delay = 90
        else:
            logging.warning(f'Cannot get refresh thread for league platform {self.league.platform.value}')
            return
        if self.demo_source:
            last_time = datetime.now() - timedelta(days=10)
            #speed up loop refresh for demo
            delay = 10
        logging.info('Entering Draft Refresh Loop')
        self.run_event.clear()
        while(not self.run_event.is_set()):
            drafted = []
            cut = []
            try:
                if self.league.platform == Platform.OTTONEU:
                    drafted, cut, last_time = ottoneu_services.resolve_draft_results_against_rosters(self.league, self.value_calculation, last_time, self.inflation_method, self.demo_source)
                        
                elif self.league.platform == Platform.YAHOO:
                    try:
                        drafted, cut = yahoo_services.resolve_draft_results_against_rosters(self.league, self.value_calculation, self.inflation_method, self.demo_source)
                    except HTTPError:
                        logging.error('Rate limited by Yahoo')
                else:
                    #do nothing
                    continue
            except Exception as Argument:
                logging.exception('Exception processing transaction.')
            finally:
                if drafted or cut:
                    for player in drafted:
                        self.rostered_ids.append(player.index)
                    for player in cut:
                        self.rostered_ids.remove(player.index)
                    self.queue.put(('data', (drafted, cut)))
                    self.inflation = self.league.inflation
                    league_services.calculate_league_table(self.league, self.value_calculation, False, self.inflation)
                self.run_event.wait(delay)
        logging.info('Exiting Draft Refresh Loop')

    def __toggle_show_drafted(self) -> None:
        self.__show_hide_toggle(self.rostered_ids, self.rostered_detached_id_map, self.show_drafted_players.get())
    
    def __toggle_show_removed(self) -> None:
        self.__show_hide_toggle(self.removed_players, self.removed_detached_id_map, self.show_removed_players.get())
    
    def __show_hide_toggle(self, id_list:List[int], detached_map:Dict[ScrollableTreeFrame, List[str]], show:bool) -> None:
        if show:
            for view, row_list in detached_map.items():
                for row_id in row_list:
                    view.table.reattach(row_id, '', tk.END)
                row_list.clear()
                view.table.resort()
            self.__update_table_inflations()
        else:
            for p_id in id_list:
                str_pid = str(p_id)
                if str_pid in self.overall_view.table.get_children():
                    if self.overall_view in detached_map:
                        row_list = detached_map.get(self.overall_view)
                    else:
                        row_list = []
                        detached_map[self.overall_view] = row_list
                    row_list.append(str_pid)
                    self.overall_view.table.detach(str_pid)
                for _, view in self.pos_view.items():
                    if str_pid in view.table.get_children():
                        if view in detached_map:
                            row_list = detached_map.get(view)
                        else:
                            row_list = []
                            detached_map[view] = row_list
                        row_list.append(str_pid)
                        view.table.detach(str_pid)

    def __refresh_views(self, drafted:List[Player]=None, cut:List[Player]=None):
        if self.league.is_salary_cap():
            self.inflation_str_var.set(f'Inflation: {"{:.1f}".format(self.inflation*100)}%')

        if drafted is not None:
            for dp in drafted:
                dp_ind = str(dp.index)
                tags = self.__get_row_tags(dp.index)
                if dp_ind in self.overall_view.table.get_children():
                    self.overall_view.table.item(dp_ind, tags=tags)
                    if not self.show_drafted_players.get():
                        self.overall_view.table.detach(dp_ind)
                        self.rostered_detached_id_map.get(self.overall_view).append(dp_ind)
                
                for _, view in self.pos_view.items():
                    if dp_ind in view.table.get_children():
                        view.table.item(dp_ind, tags=tags)
                        if not self.show_drafted_players.get():
                            view.table.detach(dp_ind)
                            self.rostered_detached_id_map.get(view).append(dp_ind)
        
        if cut is not None:
            for cp in cut:
                cp_ind = str(cp.index)
                tags = self.__get_row_tags(cp.index)
                if cp_ind in self.overall_view.table.get_children():
                    self.overall_view.table.item(cp_ind, tags=tags)
                    if not self.show_drafted_players.get():
                        self.overall_view.table.reattach(cp_ind, '', tk.END)
                        if cp_ind in self.rostered_detached_id_map.get(self.overall_view):
                            self.rostered_detached_id_map.get(self.overall_view).remove(cp_ind)
                
                for _, view in self.pos_view.items():
                    if cp_ind in view.table.get_children():
                        view.table.item(cp_ind, tags=tags)
                        if not self.show_drafted_players.get():
                            view.table.reattach(cp_ind, '', tk.END)
                            if cp_ind in self.rostered_detached_id_map.get(view):
                                self.rostered_detached_id_map.get(view).remove(cp_ind)

        if drafted is not None or len(drafted) > 0 or cut is not None or len(cut) > 0:
            self.__update_table_inflations()
        
        self.search_view.table.refresh()
        self.__refresh_planning_frame()
        self.standings.refresh()
    
    def __update_table_inflations(self):
        for child in self.overall_view.table.get_children():
            pv = self.value_calculation.get_player_value(int(child), Position.OVERALL)
            self.overall_view.table.set(child, 2, self.__get_inflated_cost(pv))
        self.overall_view.table.resort()
        for pos, view in self.pos_view.items():
            for child in view.table.get_children():
                pv = self.value_calculation.get_player_value(int(child), pos)
                view.table.set(child, 2, self.__get_inflated_cost(pv))
            view.table.resort()
    
    def __get_inflated_cost(self, pv:PlayerValue) -> str:
        if pv is None:
            val = 0
        else:
            val = pv.value
        if val < 1:
            inf_cost = f'${"{:.0f}".format(val)}'
        elif self.inflation_method == InflationMethod.CONVENTIONAL:
            inf_cost = '$' + "{:.0f}".format(val * (self.inflation + 1))
        else:
            inf_cost = '$' + "{:.0f}".format((val-1) * (self.inflation + 1) + 1)
        return inf_cost

    def __get_stock_player_row(self, pv:PlayerValue) -> tuple:
        name = pv.player.name
        if self.league.is_salary_cap():
            value = '$' + "{:.0f}".format(pv.value)
            inf_cost = self.__get_inflated_cost(pv)
            rank = 0
            round = 0
        else:
            value = 0
            inf_cost = 0
            rank = pv.rank
            round = self.player_to_round_map.get(pv.player.index, 'NR')
        if pv.player.custom_positions:
            position = pv.player.custom_positions
        else:
            position = pv.player.position
        team = pv.player.team
        return (name, value, inf_cost, rank, round, position, team)

    def __refresh_overall_view(self):
        self.rostered_detached_id_map[self.overall_view] = []
        self.removed_detached_id_map[self.overall_view] = []
        if self.value_calculation.format == ScoringFormat.CUSTOM:
            custom_scoring = custom_scoring_services.get_scoring_format(int(self.value_calculation.get_input(CalculationDataType.CUSTOM_SCORING_FORMAT)))
        else:
            custom_scoring = None
        for pv in self.value_calculation.get_position_values(Position.OVERALL):
            stock_player = self.__get_stock_player_row(pv)
            if self.value_calculation.projection is None:
                #TODO: update this
                ...
            else:
                pp = self.value_calculation.projection.get_player_projection(pv.player.index)
                h_points = calculation_services.get_points(pp, Position.OFFENSE, sabr=False, custom_format=custom_scoring)
                p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=False, custom_format=custom_scoring)
                sp_points = calculation_services.get_points(pp, Position.PITCHER, sabr=True, custom_format=custom_scoring)
                pts = "{:.1f}".format(h_points + p_points)
                sabr_pts = "{:.1f}".format(h_points + sp_points)
                h_g = pp.get_stat(StatType.G_HIT)
                pa = pp.get_stat(StatType.PA)
                try:
                    ppg = "{:.2f}".format(h_points/h_g)
                    hppg = "{:.2f}".format(h_points/h_g)
                    pppa = "{:.2f}".format(h_points/pa)
                except (ZeroDivisionError, TypeError):
                    ppg = hppg = pppa = "0.00"
                ip = pp.get_stat(StatType.IP)
                p_g = pp.get_stat(StatType.G_PIT)
                try:
                    pip = "{:.2f}".format(p_points/ip)
                    spip = "{:.2f}".format(sp_points/ip)
                    pppg = "{:.2f}".format(p_points/p_g)
                    spppg = "{:.2f}".format(sp_points/p_g)
                except (ZeroDivisionError, TypeError):
                    pip = spip = pppg = spppg = "0.00"
            sal_tup = self.__get_salary_tuple(pv.player)
            tags = self.__get_row_tags(pv.player.index)
            self.overall_view.table.insert('', tk.END, iid=pv.player.index, values=stock_player + (pts, sabr_pts, ppg, hppg, pppa, pip, spip, pppg, spppg) + sal_tup, tags=tags)

    def __refresh_pos_table(self, pos:Position):
        self.rostered_detached_id_map[self.pos_view[pos]] = []
        self.removed_detached_id_map[self.pos_view[pos]] = []
        if self.value_calculation.format == ScoringFormat.CUSTOM:
            custom_scoring = custom_scoring_services.get_scoring_format(int(self.value_calculation.get_input(CalculationDataType.CUSTOM_SCORING_FORMAT)))
        else:
            custom_scoring = None
        for pv in self.value_calculation.get_position_values(pos):
            stock_player = self.__get_stock_player_row(pv)
            sal_tup = self.__get_salary_tuple(pv.player)
            tags = self.__get_row_tags(pv.player.index)
            point_cols = []
            if self.value_calculation.projection is None:
                ...
            elif self.value_calculation.projection.type == ProjectionType.VALUE_DERIVED:
                ...
            else:
                pp = self.value_calculation.projection.get_player_projection(pv.player.index)
                points = calculation_services.get_points(pp, pos, sabr=False, custom_format=custom_scoring)
                point_cols.append("{:.1f}".format(points))
                
                if pos.offense:
                    games = pp.get_stat(StatType.G_HIT)
                    pa = pp.get_stat(StatType.PA)
                    try:
                        point_cols.append("{:.2f}".format(points/games))
                        point_cols.append("{:.2f}".format(points/pa))
                    except (ZeroDivisionError, TypeError):
                        point_cols.append("0.00")
                        point_cols.append("0.00")
                    stats = []
                    for col in all_hitting_stats:
                        stat_type = StatType.get_hit_stattype(col)
                        if stat_type is not None:
                            stat = pp.get_stat(stat_type)
                            if stat is None:
                                stats.append(stat_type.format.format(0))
                            else:
                                stats.append(stat_type.format.format(stat))
                    
                else:
                    s_points = calculation_services.get_points(pp, pos, sabr=True, custom_format=custom_scoring)
                    point_cols.append("{:.1f}".format(s_points))
                    games = pp.get_stat(StatType.G_PIT)
                    ip = pp.get_stat(StatType.IP)
                    try:
                        point_cols.append("{:.2f}".format(points/ip))
                        point_cols.append("{:.2f}".format(s_points/ip))
                    except (ZeroDivisionError, TypeError):
                        point_cols.append("0.00")
                        point_cols.append("0.00")
                    try:
                        point_cols.append("{:.2f}".format(points/games))
                        point_cols.append("{:.2f}".format(s_points/games))
                    except (ZeroDivisionError, TypeError):
                        point_cols.append("0.00")
                        point_cols.append("0.00")
                    stats = []
                    for col in all_pitching_stats:
                        stat_type = StatType.get_pitch_stattype(col)
                        if stat_type is not None:
                            stat = pp.get_stat(stat_type)
                            if stat is None:
                                stats.append(stat_type.format.format(0))
                            else:
                                stats.append(stat_type.format.format(stat))
                    
            self.pos_view[pos].table.insert('', tk.END, iid=pv.player.index, values=stock_player + tuple(point_cols) + sal_tup + tuple(stats), tags=tags)
    
    def __get_salary_tuple(self, player:Player):
        if self.league.platform == Platform.OTTONEU:
            si = player.get_salary_info_for_format(self.league.format)
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
        return ('$0', '$0', '0%')

    def __get_row_tags(self, playerid):
        if self.league.is_rostered(player_id=playerid):
            return ('rostered',)
        if self.draft.get_target_by_player(player_id=playerid) is not None:
            return ('targeted',)
        if playerid in self.removed_players:
            return ('removed',)
        return ''
    
    def __set_row_colors(self, table: Table, targets=True):
        table.tag_configure('rostered', background='#A6A6A6')
        table.tag_configure('rostered', foreground='#5A5A5A')
        table.tag_configure('removed', background='#FFCCCB')
        if targets:
            table.tag_configure('targeted', background='#FCE19D')

    def __update_player_search(self):
        text = self.search_string.get().upper()
        if text == '' or len(text) == 1 or (self.search_unrostered_bv.get() and len(text) < 3):
            players = [] 
        else:
            players = player_services.search_by_name(text)
        if self.value_calculation.format == ScoringFormat.CUSTOM:
            custom_scoring = custom_scoring_services.get_scoring_format(int(self.value_calculation.get_input(CalculationDataType.CUSTOM_SCORING_FORMAT)))
        else:
            custom_scoring = None
        for player in players:
            if self.league.platform == Platform.OTTONEU:
                si = player.get_salary_info_for_format(self.league.format)
                if (si is None or si.roster_percentage == 0) and not self.search_unrostered_bv.get():
                    continue
            elif player.index not in self.value_calculation.value_dict and not self.search_unrostered_bv.get():
                continue
            else:
                si = None
                
            id = player.index
            name = player.name
            if player.custom_positions:
                pos = player.custom_positions
            else:
                pos = player.position
            team = player.team

            pv = self.value_calculation.get_player_value(id, Position.OVERALL)
            if pv is None:
                value = 'NR'
                inf_cost = 'NR'
                rank = 'NR'
                round = 'NR'
            else:
                if self.league.is_salary_cap():
                    value = '$' + "{:.0f}".format(pv.value)
                    inf_cost = self.__get_inflated_cost(pv)
                    rank = 0
                    round = 0
                else:
                    value = 0
                    inf_cost = 0
                    rank = pv.rank
                    round = self.player_to_round_map.get(pv.player.index, 'NR')

            salary = f'${self.league.get_player_salary(player.index)}'

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
                        h_pts = calculation_services.get_points(pp, Position.OFFENSE, custom_format=custom_scoring)
                        p_pts = calculation_services.get_points(pp, Position.PITCHER, False, custom_format=custom_scoring)
                        s_p_pts = calculation_services.get_points(pp, Position.PITCHER, True, custom_format=custom_scoring)
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

            tags = self.__get_row_tags(id)
            self.search_view.table.insert('', tk.END, iid=str(id), tags=tags, values=(name, value, salary, inf_cost,rank,round,pos, team, pts, spts, ppg, hppg, pppa, pip, spip, pppg, spppg, roster_percent))
   
    def __refresh_planning_frame(self):
        self.target_table.table.refresh()

    def __refresh_targets(self):
        for target in self.draft.targets:
            id = target.player_id
            name = target.player.name
            t_price = f'${target.price}'
            pv = self.value_calculation.get_player_value(id, pos=Position.OVERALL)
            if pv is None:
                value = '$0'
            else:
                value = '$' + "{:.0f}".format(pv.value)
            if target.player.custom_positions:
                pos = target.player.custom_positions
            else:
                pos = target.player.position
            tags = self.__get_row_tags(id)
            self.target_table.table.insert('', tk.END, iid=id, tags=tags, values=(name, t_price, value, pos))
    
    def __initialize_draft(self, same_values=False): 
        restart = False
        if not self.run_event.is_set():
            self.__stop_draft_monitor()
        prog = progress.ProgressDialog(self.parent, 'Initializing Draft Session')

        if self.rostered_detached_id_map is not None and len(self.rostered_detached_id_map) > 0:
            self.__show_hide_toggle(self.rostered_ids, self.rostered_detached_id_map, True)
        if self.removed_detached_id_map is not None and len(self.removed_detached_id_map) > 0:
            self.__show_hide_toggle(self.removed_players, self.removed_detached_id_map, True)

        self.rostered_ids = []
        rostered = []
        self.rostered_detached_id_map = {}
        self.removed_detached_id_map = {}
        self.player_to_round_map = {}

        if self.league.platform == Platform.YAHOO:
            for team in self.league.teams:
                team.roster_spots.clear()
            yahoo_services.resolve_draft_results_against_rosters(self.league, self.value_calculation, self.inflation_method, self.demo_source)

        for team in self.league.teams:
            for rs in team.roster_spots:
                rostered.append(rs.player)
                self.rostered_ids.append(rs.player.index)

        if self.draft.cm_draft is not None:
            self.monitor_status.set(f'Using CM Draft {self.draft.cm_draft.cm_draft_id}')
            self.monitor_status_lbl.config(fg='green')
            self.start_draft_sv.set('Refresh CM Draft')
            CreateToolTip(self.start_monitor, 'Gets the latest CouchManager draft results and applies them.')
            self.stop_draft_sv.set('Unlink CM Draft')
            self.stop_monitor['state'] = ACTIVE
            CreateToolTip(self.stop_monitor, 'Removes the connection to the CouchManagers draft for the league and reverts to the Ottoneu-only rosters.')
            if self.draft.cm_draft.setup:
                rostered.extend(self.__resolve_cm_draft_with_rosters())
            else:
                self.__check_new_cm_teams()

        if self.league.is_linked() and self.league.is_salary_cap():
            self.league.init_inflation_calc()
            self.inflation = league_services.calculate_league_inflation(self.league, self.value_calculation, self.inflation_method)
        else:
            self.inflation = 0
            self.inflation_str_var.set('')
        
        if self.league.is_salary_cap():
            self.search_view.table.sort_col = 'Value'
            self.overall_view.table.sort_col = 'Value'
            for view in self.pos_view.values():
                view.table.sort_col = 'Value'
        else:
            self.search_view.table.sort_col = 'Rank'
            self.overall_view.table.sort_col = 'Rank'
            for view in self.pos_view.values():
                view.table.sort_col = 'Rank'
        
        calculation_services.set_player_ranks(self.value_calculation)

        prog.set_task_title('Refreshing views...')
        prog.increment_completion_percent(25)
        to_remove = []
        for pos, table in self.pos_view.items():
            if pos == Position.OVERALL or pos == Position.OFFENSE or pos == Position.PITCHER: continue
            if not table: continue
            for tab_id in self.tab_control.tabs():
                item = self.tab_control.tab(tab_id)
                if item['text']==pos.value:
                    for child in self.tab_control.winfo_children():
                        if str(child) == tab_id:
                            child.destroy()
                            break
                    to_remove.append(pos)
                    break
        
        for pos in to_remove:
            del self.pos_view[pos]
        
        for rank, vc in enumerate(self.value_calculation.get_position_values(Position.OVERALL)):
            self.player_to_round_map[vc.player.index] = int((rank)/self.league.num_teams + 1)
        
        self.__create_position_tables()
        prog.increment_completion_percent(25)
        self.__set_visible_columns()

        self.standings.value_calc = self.controller.value_calculation
        self.standings.update_league(self.controller.league)
        league_services.calculate_league_table(self.league, self.value_calculation, fill_pt=False, inflation=self.inflation)
        self.standings.refresh()

        self.__populate_views()
        prog.increment_completion_percent(25)
        self.__refresh_views(drafted=rostered)

        prog.complete()
        if restart:
            self.__start_draft_monitor()
    
    def __populate_views(self):
        self.overall_view.table.refresh()
        for _, view in self.pos_view.items():
            view.table.refresh()

    def __calc_format_matches_league(self) -> bool:
        if self.league.platform == Platform.OTTONEU:
            if ScoringFormat.is_points_type(self.league.format):
                return ScoringFormat.is_points_type(self.value_calculation.format)
            return self.league.format == self.value_calculation.format
        return True

    def __set_visible_columns(self) -> None:
        if self.league.platform == Platform.OTTONEU:
            salary_cols = ('Avg. Price', 'L10 Price', 'Roster %')
        else:
            salary_cols = tuple()
        if self.league.is_salary_cap():
            player_value_cols = player_salary_cap_columns
            stock_search = ('Name','Value','Inf. Cost','Salary','Pos','Team')
        else:
            player_value_cols = player_no_salary_cap_columns
            stock_search = ('Name','Rank','Round','Pos','Team')
        stock_overall = player_value_cols + salary_cols
        if self.value_calculation.format == ScoringFormat.CUSTOM:
            custom_scoring = custom_scoring_services.get_scoring_format(int(self.value_calculation.get_input(CalculationDataType.CUSTOM_SCORING_FORMAT)))
        else:
            custom_scoring = None
        if self.value_calculation.projection is None or not self.__calc_format_matches_league():
            self.overall_view.table.set_display_columns(stock_overall)
            for _, view in self.pos_view.items():
                view.table.set_display_columns(stock_overall)
            if self.league.platform == Platform.OTTONEU:
                self.search_view.table.set_display_columns(stock_search + ('Roster %',))
            else:
                self.search_view.table.set_display_columns(stock_search)
        elif (not self.league.platform == Platform.OTTONEU and ScoringFormat.is_points_type(self.value_calculation.format)) or (custom_scoring is not None and custom_scoring.points_format) or ScoringFormat.is_points_type(self.league.format):
            if self.league.platform == Platform.OTTONEU:
                sabr = ScoringFormat.is_sabr(self.league.format)
            else:
                sabr = ScoringFormat.is_sabr(self.value_calculation.format)
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
            self.overall_view.table.set_display_columns(player_value_cols + p_points + hit_rate + pitch_rate + salary_cols)
            for pos, view in self.pos_view.items():
                if pos.offense:
                    view.table.set_display_columns(player_value_cols + ('Points',) + pos_hit_rate + salary_cols)
                else:
                    view.table.set_display_columns(player_value_cols + p_points + pitch_rate + salary_cols)
            if self.league.platform == Platform.OTTONEU:
                self.search_view.table.set_display_columns(stock_search + p_points + hit_rate + pitch_rate + ('Roster %',))
            else:
                self.search_view.table.set_display_columns(stock_search + p_points + hit_rate + pitch_rate)
        elif (not self.league.platform == Platform.OTTONEU and self.value_calculation.format == ScoringFormat.OLD_SCHOOL_5X5) or self.league.format == ScoringFormat.OLD_SCHOOL_5X5:
            self.overall_view.table.set_display_columns(stock_overall)
            for pos, view in self.pos_view.items():
                if pos.offense:
                    view.table.set_display_columns(player_value_cols + hit_5x5_cols + salary_cols)
                else:
                    view.table.set_display_columns(player_value_cols + pitch_5x5_cols + salary_cols)
            if self.league.platform == Platform.OTTONEU:
                self.search_view.table.set_display_columns(stock_search + ('Roster %',))
            else:
                self.search_view.table.set_display_columns(stock_search)
        elif (not self.league.platform == Platform.OTTONEU and self.value_calculation.format == ScoringFormat.CLASSIC_4X4) or self.league.format == ScoringFormat.CLASSIC_4X4:
            self.overall_view.table.set_display_columns(stock_overall)
            for pos, view in self.pos_view.items():
                if pos.offense:
                    view.table.set_display_columns(player_value_cols + hit_4x4_cols + salary_cols)
                else:
                    view.table.set_display_columns(player_value_cols + pitch_4x4_cols + salary_cols)
            if self.league.platform == Platform.OTTONEU:
                self.search_view.table.set_display_columns(stock_search + ('Roster %',))
            else:
                self.search_view.table.set_display_columns(stock_search)
        elif self.value_calculation.format == ScoringFormat.CUSTOM:
            self.overall_view.table.set_display_columns(stock_overall)
            hit = []
            pitch = []
            for cat in custom_scoring.stats:
                stat = cat.category
                if stat.hitter and stat.display not in player_cols:
                    hit.append(stat.display)
                if not stat.hitter and stat.display not in player_cols:
                    pitch.append(stat.display)
            for pos, view in self.pos_view.items():
                if pos.offense:
                    view.table.set_display_columns(player_value_cols + tuple(hit))
                else:
                    view.table.set_display_columns(player_value_cols + tuple(pitch))
            self.search_view.table.set_display_columns(stock_search)
        else:
            if self.league.platform == Platform.OTTONEU:
                raise Exception(f"Unknown league type {self.league.format}")
            else:
                raise Exception(f"Unhandled scoring format for non-Ottoneu League {self.value_calculation.format.short_name}")

    def league_change(self):
        while self.controller.league is None:
            self.controller.select_league()
        if self.controller.league is not None and self.league.site_id != self.controller.league.site_id:
            self.league = self.controller.league
            self.league_text_var.set(f'League {self.controller.league.name} Draft')
            if self.league.is_linked():
                self.draft = draft_services.get_draft_by_league(self.controller.league.index)
                if self.league.platform == Platform.OTTONEU:
                    self.salary_information_refresh()
            self.__initialize_draft(same_values=True)
    
    def value_change(self):
        if self.controller.value_calculation is not None and self.value_calculation != self.controller.value_calculation:
            self.value_calculation = self.controller.value_calculation
            self.starting_set = self.value_calculation.starting_set
            self.values_name.set(f'Selected Values: {self.value_calculation.name}')
            self.__initialize_draft()

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
