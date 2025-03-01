from abc import ABC, abstractmethod

class ProgressUpdater(ABC):

    @abstractmethod
    def set_task_title(self, task_title:str):
        pass

    @abstractmethod
    def increment_completion_percent(self, increment:int):
        pass

    @abstractmethod
    def set_completion_percent(self, percent:int):
        pass

    @abstractmethod
    def update_completion_percent(self):
        pass

    @abstractmethod
    def complete(self):
        pass