class InputException(Exception):
    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs