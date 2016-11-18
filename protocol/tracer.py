import enum


class TracerCodes(enum.Enum):
    new_address = 01
    

class Tracer:
    def __init__(self):
        self.code