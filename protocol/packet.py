import abc
import inspect
from collections import defaultdict
from typing import List, Dict, Optional

from protocol.packet_fields import FixedSizeInt
from protocol.tracer import Tracer

FRAME_SIZE = 11
PHYSICAL_ADDRESS_FRAMES = 2


def list_and_bitmap_frame_count(list_len: int) -> int:
    """
    Calcola quanti frame conterrebbe il percorso degli indirizzi se
    l'implementazione usasse una bitmap.

    :param list_len: La lunghezza della lista degli indirizzi
    :return: Il conto dei frame del percorso nel pacchetto
    """

    quot, rem = divmod(list_len, 11)
    return list_len + quot + int(rem > 0) + 1


class Packet(metaclass=abc.ABCMeta):

    __STATIC_FRAMES = 1

    version = FixedSizeInt(2)
    token = FixedSizeInt(3)

    def __init__(self):

        self.code_is_node_init = False
        self.code_destination_is_endpoint = False
        self.code_is_addressing_static = False

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
            for cls in inspect.getmro(type(self)) if issubclass(cls, Packet)
        )

    @abc.abstractmethod
    def _frame_increment(self):
        return self.__STATIC_FRAMES

    def damage_bit(self, frame_index=None):

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

    physical_address = FixedSizeInt(FRAME_SIZE * PHYSICAL_ADDRESS_FRAMES)

    @abc.abstractmethod
    def _frame_increment(self):
        return PHYSICAL_ADDRESS_FRAMES


class PacketWithSource(Packet):

    source_static = FixedSizeInt(FRAME_SIZE)
    source_logic = FixedSizeInt(FRAME_SIZE)

    @abc.abstractmethod
    def _frame_increment(self):
        return 2


class HelloRequestPacket(PacketWithPhysicalAddress):

    def __init__(self):
        super().__init__()

    def __repr__(self):
        return '<HelloRequestPacket addr={}>'.format(self.physical_address)

    def _frame_increment(self):
        return 0


class HelloResponsePacket(PacketWithPhysicalAddress, PacketWithSource):

    def __init__(self):
        super().__init__()

    new_static_address = FixedSizeInt(FRAME_SIZE)
    new_logic_address = FixedSizeInt(FRAME_SIZE)

    def __repr__(self):
        return '<HelloResponsePacket addr={}>'.format(self.physical_address)

    def _frame_increment(self):
        return 2


class CommunicationPacket(PacketWithSource):

    __STATIC_FRAMES = 2

    next_hop        = FixedSizeInt(FRAME_SIZE)
    payload_length  = FixedSizeInt(FRAME_SIZE)

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
    destination     = FixedSizeInt(FRAME_SIZE)
    new_logic_addr  = FixedSizeInt(FRAME_SIZE, init_value=None, optional=True)

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

        frames += len(self.noise_tables)
        frames += len(self.new_node_list)
        frames += sum(len(table) * 2 for table in self.noise_tables)

        return frames
