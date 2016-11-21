import enum
import typing

import networkx as nx
import simpy

from protocol.packet import Packet, PacketCodes, HelloRequestPacket, \
    ResponsePacket
from protocol.packet import RequestPacket
from protocol.rethunder_node import ReThunderNode
from utils.condition_var import BroadcastConditionVar
from utils.run_process_decorator import run_process
from utils.shortest_paths_tree import shortest_paths_tree



class BusyError(Exception):
    pass


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

    def __init__(self, env, transmission_speed):

        super().__init__(env, transmission_speed,
                         static_address=0, dynamic_address=0)

        self.node_graph = nx.Graph()             # type: nx.Graph
        self.__shortest_paths_tree = nx.Graph()  # type: nx.Graph
        self.__send_cond = BroadcastConditionVar(self.env)
        self.__current_message = None

    def __repr__(self):
        return '<MasterNode>'

    def send_message(self, dest_type: DestinationType, destination: int,
                     message, message_length):

        if self.__current_message is not None:
            raise BusyError

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

        if packet.response:
            yield self.__on_received_response(packet)

        raise NotImplementedError

    @run_process
    def __on_send_request(self, packet):
        raise NotImplementedError

    @run_process
    def __on_received_response(self, response_msg: ResponsePacket):

        request_msg = self.__current_message  # type: RequestPacket
        self.__current_message = None

    def __update_node_graph(self, dest, packet: ResponsePacket):

        node_graph = self.node_graph
        sptree = self.__shortest_paths_tree
        return_path = nx.shortest_path(sptree, dest, 0, 'weight')

        for source_node, noise_table in zip(return_path, packet.noise_tables):

            for dest_node, noise_level in noise_table.items():

                node_graph[source_node][dest_node]['noise'] = noise_level

        self.__shortest_paths_tree = shortest_paths_tree(node_graph, 0, 'noise')

