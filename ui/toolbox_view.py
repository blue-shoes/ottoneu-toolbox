from abc import ABC, abstractclassmethod
import tkinter as tk  

from ui.app_controller import Controller

class ToolboxView(ABC, tk.Frame):

    controller:Controller

    @abstractclassmethod
    def on_show(self) -> bool:
        pass

    @abstractclassmethod
    def leave_page(self) -> bool:
        pass

    @abstractclassmethod
    def league_change(self) -> bool:
        pass

    @abstractclassmethod
    def value_change(self) -> bool:
        pass