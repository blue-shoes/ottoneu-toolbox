import tkinter as tk     
from tkinter import *              
from tkinter import ttk 


class Start(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        main_lbl = ttk.Label(self, text = "Select a module", font='bold')
        main_lbl.grid(column=0,row=0, pady=5, columnspan=2)

        ttk.Button(self, text='Create Player Values', command=self.create_player_values_click).grid(column=0,row=1)
        ttk.Button(self, text='Run Draft Tracker', command=self.run_draft_tracker).grid(column=1,row=1)
        la_btn = ttk.Button(self, text='League Analysis', command=self.open_league_analysis)
        la_btn.grid(column=0,row=2)
        la_btn['state'] = DISABLED
        ttk.Button(self, text='Exit', command=self.exit).grid(column=1,row=2)

        self.pack()
    
    def on_show(self):
        return True
    
    def leave_page(self):
        return True

    def create_player_values_click(self):
        # TODO: Move to Create Player Values Module
        self.controller.show_player_values()

    def run_draft_tracker(self):
        self.controller.show_draft_tracker()

    def open_league_analysis(self):
        # TODO: Move to league analysis
        a = 1
    
    def exit(self):
        self.controller.exit()   

#def main():
#    try:
#        program = OttoneuToolBox()
#    except Exception as e:
#        logging.exception("Error encountered")
#        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

#if __name__ == '__main__':
#    main()