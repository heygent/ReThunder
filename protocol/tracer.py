
class Tracer:

    def __init__(self, static_addressing=False, new_address=False, offset=0):
        self.static_addressing = static_addressing
        self.new_address = new_address
        self.offset = offset

    def number_of_frames(self):
        return 2 if self.offset.bit_length() > 9 else 1

    def is_valid(self):
        return self.static_addressing or self.new_address
