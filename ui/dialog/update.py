import tkinter as tk
import webbrowser


class Dialog(tk.Toplevel):
    def __init__(self, parent, response):
        super().__init__(parent)
        self.status = False

        tk.Label(self, text='New Version Available!', font='bold').grid(row=0, column=0, columnspan=2)
        updated_version = response.json()['name']
        self.release_url = response.json()['html_url']
        notes = response.json()['body'].replace('\r\n', '\n')

        tk.Label(self, text=f'Latest version is {updated_version}').grid(row=1, column=0, columnspan=2)
        tk.Message(self, text=notes).grid(row=2, column=0, columnspan=2)
        tk.Label(self, text='Click "Get Release" to go to latest release page.').grid(row=3, column=0, columnspan=2)

        tk.Button(self, text='Get Release', command=self.get_release).grid(row=4, column=0)
        tk.Button(self, text='Continue', command=self.cancel).grid(row=4, column=1)

        self.wait_window()

    def get_release(self):
        webbrowser.open_new_tab(self.release_url)
        self.status = True
        self.destroy()

    def cancel(self):
        self.status = False
        self.destroy()
