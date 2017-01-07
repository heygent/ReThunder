import abc
import enum
import inspect
import math
from collections import defaultdict
from typing import List, Dict, Tuple

from protocol.packet_fields import FixedSizeInt

FRAME_SIZE = 11
PHYSICAL_ADDRESS_FRAMES = 2


def bitmap_frame_count(list_len: int):
    """
    Calcola quanti frame conterrebbe la bitmap corrispondente a un percorso
    di indirizzi.

    :param list_len: La lunghezza della lista degli indirizzi
    :return: La lunghezza della bitmap
    """

    return math.ceil(list_len / FRAME_SIZE)


class Packet(metaclass=abc.ABCMeta):

    __STATIC_FRAMES = 1

    version = FixedSizeInt(2)
    TOKEN_BIT_SIZE = 3
    token = FixedSizeInt(TOKEN_BIT_SIZE)

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


class PacketWithNextHop(Packet):

    next_hop = FixedSizeInt(FRAME_SIZE)

    @abc.abstractmethod
    def _frame_increment(self):
        return 1


class HelloRequestPacket(PacketWithPhysicalAddress):

    def __init__(self):
        super().__init__()

    def __repr__(self):
        return f'<HelloRequestPacket addr={self.physical_address}>'

    def _frame_increment(self):
        return 0


class HelloResponsePacket(PacketWithPhysicalAddress, PacketWithSource):

    def __init__(self):
        super().__init__()

    new_static_address = FixedSizeInt(FRAME_SIZE)
    new_logic_address = FixedSizeInt(FRAME_SIZE)

    def __repr__(self):
        return f'<HelloResponsePacket addr={self.physical_address}>'

    def _frame_increment(self):
        return 2


class AckPacket(PacketWithNextHop):

    def __init__(self, of=None):

        super().__init__()

        if of is not None:

            self.code_destination_is_endpoint = of.code_destination_is_endpoint
            self.code_is_addressing_static = of.code_is_addressing_static
            self.code_is_node_init = of.code_is_node_init
            self.token = of.token
            self.next_hop = of.source_static

    def __repr__(self):
        return f'<AckPacket tok={self.token} dest={self.next_hop}>'

    def _frame_increment(self):
        return 0


class CommunicationPacket(PacketWithSource, PacketWithNextHop):

    __STATIC_FRAMES = 1

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


class AddressType(enum.Enum):
    logic = 0
    static = 1


class RequestPacket(CommunicationPacket):

    __STATIC_FRAMES = 3

    destination     = FixedSizeInt(FRAME_SIZE)

    def __init__(self):

        super().__init__()

        self.path: List[Tuple[AddressType, int]] = None
        self.new_logic_addresses: Dict[int, int] = None

    def __repr__(self):
        return f'<RequestPacket source={self.source_static}' \
               f'next_hop={self.next_hop}>'

    def _frame_increment(self):

        frames = self.__STATIC_FRAMES
        path_len = len(self.path)
        frames += path_len + bitmap_frame_count(path_len)
        frames += len(self.new_logic_addresses) * 2

        return frames


class ResponsePacket(CommunicationPacket):

    __STATIC_FRAMES = 2

    def __init__(self):
        super().__init__()
        self.noise_tables: List[Dict[int, int]] = []
        self.new_node_list: List[int] = []

    def __repr__(self):
        return f'<ResponsePacket source={self.source_static} ' \
               f'next_hop={self.next_hop}>'

    def _frame_increment(self):

        frames = self.__STATIC_FRAMES

        frames += len(self.noise_tables)
        frames += len(self.new_node_list)
        frames += sum(len(table) * 2 for table in self.noise_tables)

        return frames
