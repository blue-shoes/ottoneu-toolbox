class InputException(Exception):
    '''An exception for passing information about exceptions related to user UI input.'''
    def __init__(self, validation_msgs, *args: object) -> None:
        super().__init__(*args)
        self.validation_msgs = validation_msgs