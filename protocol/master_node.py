import enum
import typing

import networkx as nx
import simpy

from protocol.packet import Packet, PacketCodes, HelloRequestPacket
from protocol.rethunder_node import ReThunderNode
from utils.condition_var import BroadcastConditionVar
from utils.run_process_decorator import run_process
from utils.shortest_paths_tree import shortest_paths_tree

SlaveNodeData = typing.NamedTuple(
    'SlaveNodeData', (
        ('mac_address', int),
        ('static_address', int),
        ('logic_address', int),
        ('effective_address', int)
    )
)


class DestinationType(enum.Enum):
    physical = 0
    static   = 1
    dynamic  = 2


class MasterNode(ReThunderNode):

    static_address = 0

    def __init__(self, env, transmission_speed):

        super().__init__(env, transmission_speed)

        self.__nodes_graph = nx.Graph()
        self.__shortest_paths_tree = nx.Graph()
        self.__send_cond = BroadcastConditionVar(self.env)
        self.__waiting_for_response = set()

    def send_message(self, dest_type: DestinationType, destination: int,
                     message, message_length):
        self.__send_cond.broadcast((dest_type, destination, message,
                                    message_length))

    def send_packet(self, packet):
        self.__send_cond.broadcast(packet)

    @run_process
    def run(self):
        env = self.env

        while True:
            send_ev = self.__send_cond.wait()      # type: simpy.Event
            recv_ev = self._receive_packet_proc()  # type: simpy.Event

            events = (send_ev, recv_ev)

            yield env.any_of(events)

            # if the events happen at the same time unit, let them all be
            # processed before proceeding
            yield env.timeout(0)

            assert any(e.processed for e in events), "Spurious wake"

            if send_ev.processed:
                yield self.__on_send_request(send_ev.value)

            if recv_ev.processed:
                yield self.__on_reception(recv_ev.value)

    # noinspection PyTypeChecker
    @run_process
    def __on_reception(self, packet):

        if not isinstance(packet, Packet):
            raise TypeError(
                'A MasterNode received something different than a Packet.'
            )

        if packet.code == PacketCodes.hello:
            yield self.__on_received_hello(packet)

        if packet.response:
            pass

        raise NotImplemented

    @run_process
    def __on_send_request(self, packet):
        raise NotImplemented

    @run_process
    def __on_received_hello(self, packet: HelloRequestPacket):
        raise NotImplemented
