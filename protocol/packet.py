import enum
from collections import defaultdict
from typing import Dict, List, Optional

from protocol.packet_fields import FlagField, DataField, FixedSizeInt


class PacketCodes(enum.Enum):
    hello = 0b1111
    discovery = 0b0000


class Packet:

    heading     = FixedSizeInt(11)
    version     = DataField('heading', 9, 2)
    ack         = FlagField('heading', 8)
    response    = FlagField('heading', 7)
    code        = DataField('heading', 3, 4)
    token       = DataField('heading', 0, 3)

    source_static     = FixedSizeInt(11)
    hello_mac_address = source_static

    source_dynamic  = FixedSizeInt(11)
    destination     = FixedSizeInt(11)

    payload_length  = FixedSizeInt(11)
    new_static_addr = payload_length

    next_hop        = FixedSizeInt(11, None, True)
    new_logic_addr  = FixedSizeInt(11, None, True)

    code_is_node_init       = FlagField('code', 3)
    code_has_path           = FlagField('code', 2)
    code_is_dest_static     = FlagField('code', 1)
    code_has_new_logic_addr = FlagField('code', 0)

    def __init__(self):

        self.tracers_list = None   # type: Optional[List[int]]
        self.path = None           # type: Optional[List[int]]
        self.payload = None
        self.noise_table = {}      # type: Dict[int, int]
        self.new_node_list = None  # type: Optional[List[int]]

        self.frame_errors = defaultdict(lambda: 0)  # type: Dict[int, int]

    @property
    def number_of_frames(self):

        if self.code == PacketCodes.hello:
            return 2

        frames = 5

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
