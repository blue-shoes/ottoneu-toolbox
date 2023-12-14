import tkinter as tk     
from tkinter import *              
from tkinter import font
from ui.dialog.wizard import wizard
import logging
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL, OK
import os
import webbrowser
import json

from services import yahoo_services

class Dialog(wizard.Dialog):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Set up Yahoo Service')
        return self.wizard

class Wizard(wizard.Wizard):

    oauth:yahoo_services.Custom_OAuth2

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.step0 = Step0(self)
        self.step1 = Step1(self)
        self.step2 = Step2(self)
        self.step3 = Step3(self)
        self.steps.append(self.step0)
        self.steps.append(self.step1)
        self.steps.append(self.step2)
        self.steps.append(self.step3)

        self.show_step(0)
    
    def cancel(self):
        self.league = None
        self.parent.status = CANCEL
        super().cancel()
    
    def finish(self):
        self.parent.validate_msg = None
        yahoo_services.set_credentials(self.oauth, self.step3.verifier_sv.get())
        if os.path.exists('conf/token.json'):
            self.parent.status = OK
            return super().finish()
        self.parent.validate_msg = f'The token file was not successfully created. Please try again.'
        return False

    def next(self):
        if self.current_step == 0:
            webbrowser.open("https://developer.yahoo.com/apps/create/")
        super().next()

class Step0(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Set up Yahoo! Fantasy Service', font='bold').grid(row=0, column=0, sticky=W)

        tk.Label(self, text='The Ottoneu Toolbox retrieves data from Yahoo! using the \n\
                 Yahoo Fantasy Sports API. Use of this requires the setup of an app \n\
                 through Yahoo developer for authentication. The following wizard will \
                 \ndirect the user through this process. Click \"Next\" to open the required \n\
                 web page and proceed. Instructions for each page will be provided in the wizard.').grid(row=1, column=0, rowspan=5, sticky=W)
    
    def validate(self):
        return True
    
    def on_show(self):
        return True
    
class Step1(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Set up Yahoo! Fantasy Service', font='bold').grid(row=0, column=0, sticky=W)
        tk.Label(self, text='Set the following inputs (others may be left blank or as defaults)').grid(row=1, column=0, columnspan=2, sticky=W)
        tk.Label(self, text='Application Name', font='bold').grid(row=2, column=0, sticky=W)
        tk.Label(self, text='Ottoneu-Toolbox').grid(row=2, column=1, sticky=W)
        tk.Label(self, text='Redirect URI(s)', font='bold').grid(row=3, column=0, sticky=W)
        tk.Label(self, text='https://localhost:8080').grid(row=3, column=1, sticky=W)
        tk.Label(self, text='Under \"API Permissions\", select \"Fantasy Sports\"').grid(row=4, column=0, columnspan=2, sticky=W)
        tk.Label(self, text='Click \"Create App\" on the webpage and \"Next\" in the wizard.').grid(row=6, column=0, columnspan=2, sticky=W)

    def validate(self):
        return True
    
    def on_show(self):
        return True

class Step2(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Set up Yahoo! Fantasy Service', font='bold').grid(row=0, column=0, sticky=W)
        tk.Label(self, text='Enter the following information from the created app').grid(row=1, column=0, columnspan=2, sticky=W)
        tk.Label(self, text='Client ID', font='bold').grid(row=2, column=0, sticky=W)
        self.client_id_sv = StringVar()
        tk.Entry(self, textvariable=self.client_id_sv).grid(row=2, column=1, columnspan=2, sticky=W)
        tk.Label(self, text='Client Secret', font='bold').grid(row=3, column=0, sticky=W)
        self.client_secret_sv = StringVar()
        tk.Entry(self, textvariable=self.client_secret_sv).grid(row=3, column=1, columnspan=2, sticky=W)
        tk.Label(self, text='Clicking \"Next\" in the wizard will open a new webpage if authentication is successful.\n\
                 It will ask for read permission. Click Yes and proceed to the next page.').grid(row=6, column=0, columnspan=2, sticky=W)
    
    def validate(self):
        if len(self.client_id_sv.get()) == 0 or len(self.client_secret_sv.get()) == 0:
            return False
        client_dict = {}
        client_dict['consumer_key'] = self.client_id_sv.get()
        client_dict['consumer_secret'] = self.client_secret_sv.get()
        with open('conf/private.json', 'w') as private:
            json.dump(client_dict, private)
        try:
            self.parent.oauth = yahoo_services.init_oauth()
        except Exception as Argument:
            logging.exception('Error creating OAuth2')
            mb.showerror('Error Authenticating', 'There was an error creating an authentication token for the service. Confirm the Client ID and Secret were entered correctly.')
            return False
        return True
    
    def on_show(self):
        return True

class Step3(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        tk.Label(self, text='Set up Yahoo! Fantasy Service', font='bold').grid(row=0, column=0, sticky=W)
        tk.Label(self, text='Enter the following information from the opened webpage').grid(row=1, column=0, columnspan=2, sticky=W)
        tk.Label(self, text='Verifier', font='bold').grid(row=2, column=0, sticky=W)
        self.verifier_sv = StringVar()
        tk.Entry(self, textvariable=self.verifier_sv).grid(row=2, column=1, sticky=W)
    
    def on_show(self):
        return True