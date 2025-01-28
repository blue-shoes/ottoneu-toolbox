from abc import ABC, abstractclassmethod
import threading
import configparser

from domain.domain import ValueCalculation, League


class Controller(ABC):
    value_calculation: ValueCalculation
    league: League
    demo_source: bool
    run_event: threading.Event
    preferences: configparser.ConfigParser
    resource_path: str

    @abstractclassmethod
    def select_league(self, yahoo_refresh: bool = True) -> None:
        pass

    @abstractclassmethod
    def select_value_set(self) -> None:
        pass
