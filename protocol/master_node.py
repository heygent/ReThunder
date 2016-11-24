import logging

import networkx as nx
import simpy

from protocol.packet import Packet, ResponsePacket
from protocol.rethunder_node import ReThunderNode
from utils.condition_var import BroadcastConditionVar
from utils.run_process_decorator import run_process
from utils.graph import shortest_paths_tree

logger = logging.getLogger(__name__)


class BusyError(Exception):
    pass


class MasterNode(ReThunderNode):

    def __init__(self, env, transmission_speed, application):

        super().__init__(env, transmission_speed,
                         static_address=0, dynamic_address=0)

        self.node_graph = nx.Graph()  # type: nx.Graph
        self.application = application
        # todo inizializza albero
        self.__sptree = None  # type: nx.DiGraph
        self.__send_cond = BroadcastConditionVar(self.env)
        self.__current_message = None

    def __repr__(self):
        return '<MasterNode>'

    def __switch_logic_addresses(self, log_addr_a, log_addr_b):
        raise NotImplementedError

    def __readdress_nodes(self):

        sptree = self.__sptree  # type: nx.DiGraph
        assert nx.is_tree(sptree)

        next_previous_address = 0

        for current_address in range(1, 1 << 11):

            if current_address not in sptree:
                continue

            previous_address = next_previous_address
            next_previous_address = current_address

            while True:
                father, = sptree.predecessors(current_address)

                if father > current_address:
                    self.__switch_logic_addresses(current_address, father)
                else:
                    break

            if father == previous_address:
                continue

            try:
                greatest_son = max(sptree.successors_iter(previous_address))
                self.__switch_logic_addresses(current_address, greatest_son)
                continue

            except ValueError:
                pass

            try:
                ancestor_of_previous, = sptree.predecessors(previous_address)
            except IndexError:
                continue

            while ancestor_of_previous != 0 and father != ancestor_of_previous:

                greatest_son = max(sptree.successors_iter(ancestor_of_previous))

                if greatest_son > current_address:
                    self.__switch_logic_addresses(current_address, greatest_son)
                    continue

                ancestor_of_previous, = sptree.predecessors(previous_address)

    def send_message(self, destination_static_addr: int,
                     message, message_length):

        if self.__current_message is not None:
            raise BusyError("{} is waiting for another message "
                            "response.".format(self))

        self.__send_cond.broadcast((destination_static_addr, message,
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
            logger.error(
                '{} received something different than a Packet.'.format(self)
            )
            return

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
