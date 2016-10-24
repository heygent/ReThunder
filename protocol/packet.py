from collections import defaultdict
from typing import Dict
from typing import List
from typing import Optional, Tuple


class FixedSizeInt:

    def __init__(self, max_size, init_value: Optional[int]=0, optional=False):

        self.__max_size = max_size  # type: int
        self.__optional = optional  # type: bool
        self.__validate(init_value)
        self.__value = init_value   # type: Optional[int]

    def __get__(self, instance, owner):
        return self.__value

    def __set__(self, instance, value):
        self.__validate(value)
        self.__value = value

    def __validate(self, value):

        if value is None:
            if not self.__optional:
                raise ValueError("Value can't be None")
        elif value.bit_length() > self.__max_size:
            raise ValueError("Integer too big for this field")


class Packet:

    version     = FixedSizeInt(2)
    code        = FixedSizeInt(4)
    token       = FixedSizeInt(3)

    source_static   = FixedSizeInt(11)
    source_dynamic  = FixedSizeInt(11)
    destination     = FixedSizeInt(11)

    payload_length  = FixedSizeInt(11)
    new_static_addr = payload_length

    next_hop        = FixedSizeInt(11, None, True)
    new_logic_addr  = FixedSizeInt(11, None, True)

    def __init__(self):

        self.response = False      # type: bool
        self.ack = False           # type: bool
        self.tracers_list = None   # type: Optional[List[int]]
        self.path = None           # type: Optional[List[int]]
        self.payload = None
        self.noise_table = {}      # type: Dict[int, int]
        self.new_node_list = None  # type: Optional[List[int]]

        self.frame_errors = defaultdict(lambda: 0)  # type: Dict[int, int]

    @property
    def number_of_frames(self):

        frames = 6

        for frame in (self.next_hop, self.new_logic_addr):
            if frame is not None:
                frames += 1

        collections = ((self.tracers_list, 1), (self.new_node_list, 1),
                       (self.path, 1), (self.noise_table, 2))

        for collection, multiplier in collections:
            try:
                frames += len(collection) * multiplier
            except TypeError:
                pass

        # noinspection PyTypeChecker
        quot, remainder = divmod(self.payload_length, 4)
        frames += quot * 3 + remainder

        return frames

    def damage_bit(self, frame_index):

        if not 0 <= frame_index < self.number_of_frames:
            raise IndexError('Frame index out of range')

        self.frame_errors[frame_index] += 1

