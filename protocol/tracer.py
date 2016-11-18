import enum


class TracerCodes(enum.Enum):
    new_address = 0b01
    static_addressing = 0b10


class Tracer:

    def __init__(self, code, offset):
        self.code = code
        self.offset = offset

    def number_of_frames(self):
        return 2 if self.offset.bit_length() > 9 else 1
