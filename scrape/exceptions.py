class DownloadException(Exception):
    """Exceptions related to issues downloading files from the browser."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class BrowserTypeException(Exception):
    """Exceptions related to the browser type used for scrapting."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class FangraphsException(Exception):
    """Exceptions related to scraping FanGraphs data."""

    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs


class OttoneuException(Exception):
    """Exceptions related to scraping Ottoneu data."""

    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs


class CouchManagersException(Exception):
    """Exceptions related to scraping CouchManagers data."""

    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs


class DavenportException(Exception):
    """Exceptions related to scraping Davenport data."""

    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs
