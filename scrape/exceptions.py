class DownloadException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)
class BrowserTypeException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)
class FangraphsException(Exception):
    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs
class OttoneuException(Exception):
    pass