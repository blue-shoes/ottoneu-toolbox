class DownloadException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)
class BrowserTypeException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)
class FangraphsException(Exception):
    pass
class OttoneuException(Exception):
    pass