import abc
import enum
import inspect
from collections import defaultdict
from itertools import dropwhile
from typing import List, Dict, Optional

from protocol.packet_fields import FlagField, DataField, FixedSizeInt
from protocol.tracer import Tracer

PHYSICAL_ADDRESS_FRAMES = 2


class PacketCodes(enum.Enum):
    hello = 0b1111
    hello_response = 0b0011
    discovery = 0b0000


class Packet(metaclass=abc.ABCMeta):

    __STATIC_FRAMES = 1

    heading     = FixedSizeInt(11)
    version     = DataField('heading', 9, 2)
    ack         = FlagField('heading', 8)
    response    = FlagField('heading', 7)
    code        = DataField('heading', 3, 4)
    token       = DataField('heading', 0, 3)

    code_is_node_init            = FlagField('code', 3)
    code_destination_is_endpoint = FlagField('code', 2)
    code_is_addressing_static    = FlagField('code', 1)
    code_has_new_logic_addr      = FlagField('code', 0)

    def __init__(self):
        self.__frame_errors = defaultdict(int)
        self.__frame_errors_view = self.__frame_errors.items()

    def number_of_frames(self):
        """
        Chiama _frame_increment per ogni classe nella gerarchia delle classi.
        Somma i valori che restituiscono e restituisce il risultato.

        :return: Il numero di frame di cui il pacchetto è composto.
        """

        # noinspection PyProtectedMember
        return sum(
            cls._frame_increment(self)
            for cls in dropwhile(lambda c: not issubclass(c, Packet),
                                 reversed(inspect.getmro(type(self))))
        )

    @abc.abstractmethod
    def _frame_increment(self):
        return self.__STATIC_FRAMES

    def damage_bit(self, frame_index):

        if not 0 <= frame_index < self.number_of_frames():
            raise IndexError('Frame index out of range')

        self.__frame_errors[frame_index] += 1

    def damaged_frames(self):
        return self.__frame_errors_view

    def frame_error_average(self):

        frame_errors = sum(max(error_count, 2)
                           for error_count in self.__frame_errors.values())

        return frame_errors / self.number_of_frames()

    def is_readable(self):
        return all(errors < 2 for errors in self.__frame_errors.values())


class PacketWithPhysicalAddress(Packet):

    physical_address = FixedSizeInt(11 * PHYSICAL_ADDRESS_FRAMES)

    @abc.abstractmethod
    def _frame_increment(self):
        return PHYSICAL_ADDRESS_FRAMES


class PacketWithSource(Packet):

    source_static    = FixedSizeInt(11)
    source_logic     = FixedSizeInt(11)

    @abc.abstractmethod
    def _frame_increment(self):
        return 2


class HelloRequestPacket(PacketWithPhysicalAddress):

    def __init__(self):
        super().__init__()
        self.code = PacketCodes.hello

    def _frame_increment(self):
        return 0


class HelloResponsePacket(PacketWithPhysicalAddress, PacketWithSource):

    def __init__(self):
        super().__init__()
        self.code = PacketCodes.hello_response

    new_static_address = FixedSizeInt(11)
    new_logic_address = FixedSizeInt(11)

    def _frame_increment(self):
        return 2


class CommunicationPacket(PacketWithSource):

    __STATIC_FRAMES = 2

    next_hop        = FixedSizeInt(11)
    payload_length  = FixedSizeInt(11)

    def __init__(self):
        super().__init__()
        self.payload = None

    @abc.abstractmethod
    def _frame_increment(self):
        # todo sistema numero frame rispetto campo lunghezza

        frames = self.__STATIC_FRAMES

        # noinspection PyTypeChecker
        quot, remainder = divmod(self.payload_length, 4)
        frames += quot * 3 + remainder

        return frames


class RequestPacket(CommunicationPacket):

    __STATIC_FRAMES = 3

    new_static_addr = CommunicationPacket.payload_length
    destination     = FixedSizeInt(11)
    new_logic_addr  = FixedSizeInt(11, None, True)

    def __init__(self):

        super().__init__()

        self.tracers_list = None   # type: Optional[List[Tracer]]
        self.path = None           # type: Optional[List[int]]

    def __repr__(self):
        return '<RequestPacket source={}, next_hop={}>'.format(
            self.source_static, self.next_hop
        )

    def _frame_increment(self):

        frames = self.__STATIC_FRAMES

        frames += int(self.new_static_addr is not None)
        frames += len(self.path or ())
        frames += sum(tracer.number_of_frames()
                      for tracer in self.tracers_list or ())

        return frames


class ResponsePacket(CommunicationPacket):

    __STATIC_FRAMES = 2

    def __init__(self):
        super().__init__()
        self.response = True
        self.noise_tables = []      # type: List[Dict[int, int]]
        self.new_node_list = []     # type: List[int]

    def __repr__(self):
        return '<ResponsePacket source={}, next_hop={}>'.format(
            self.source_static, self.next_hop
        )

    def _frame_increment(self):

        frames = self.__STATIC_FRAMES

        collections = ((self.noise_tables, 1),
                       *((table, 2) for table in self.noise_tables),
                       (self.new_node_list, PHYSICAL_ADDRESS_FRAMES + 1))

        frames += sum(len(collection or ()) * weight
                      for collection, weight in collections)

        return frames
