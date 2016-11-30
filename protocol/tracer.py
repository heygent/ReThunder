
NEW_ADDRESS = 0b01
STATIC_ADDRESSING = 0b10


class Tracer:

    def __init__(self, code, offset):
        self.code = code
        self.offset = offset

    def number_of_frames(self):
        return 2 if self.offset.bit_length() > 9 else 1
