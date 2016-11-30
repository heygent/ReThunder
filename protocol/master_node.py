import logging
import itertools
from typing import List, Dict

import networkx as nx
import simpy

from protocol.packet import Packet, ResponsePacket
from protocol.application import Application
from protocol.rethunder_node import ReThunderNode
from protocol.node_data_manager import NodeDataManager, NodeDataT
from utils.condition_var import BroadcastConditionVar
from utils.run_process_decorator import run_process
from utils.graph import shortest_paths_tree, preorder_tree_dfs

logger = logging.getLogger(__name__)


class BusyError(Exception):
    pass


class MasterNode(ReThunderNode):

    def __init__(self, env, transmission_speed, application):

        super().__init__(env, transmission_speed,
                         static_address=0, dynamic_address=0)

        self.node_graph = nx.Graph()    # type: nx.Graph
        self.application = application  # type: Application
        self.__sptree = None            # type: nx.DiGraph
        self.__shortest_paths = None    # type: Dict[NodeDataT, List[NodeDataT]]
        self.__send_cond = BroadcastConditionVar(self.env)
        self.__current_message = None
        self.__node_manager = NodeDataManager()

    def __repr__(self):
        return '<MasterNode>'

    def __switch_logic_addresses(self, log_addr_a, log_addr_b):
        raise NotImplementedError
    def init_from_static_addr_graph(self, addr_graph, initial_noise_value=0.5):

        if not 0 <= initial_noise_value <= 3:
            raise ValueError('initial_noise_value must be between 0 and 3')

        nodes = self.__node_manager

        # nx.relabel_nodes accepts a function for relabeling nodes.
        # It is poorly documented though, to the point that the type checker
        # fires warnings if you do.

        # noinspection PyTypeChecker
        node_graph = nx.relabel_nodes(addr_graph, nodes.create, copy=True)

        for n1, n2 in node_graph.edges_iter():
            node_graph[n1][n2]['noise'] = initial_noise_value

        self.node_graph = node_graph
        self.__update_sptree()

        addr_iter = itertools.count()

        def assign_logic_address(n: NodeDataT):
            n.logic_address = next(addr_iter)

        preorder_tree_dfs(self.__sptree, nodes[0], action=assign_logic_address)

    def __update_sptree(self):
        nodes = self.__node_manager

        shortest_paths = nx.shortest_path(self.node_graph, nodes[0], 'noise')
        self.__sptree = shortest_paths_tree(shortest_paths)
        self.__shortest_paths = shortest_paths

    def __readdress_nodes(self):

        nodes = self.__node_manager

        sptree = self.__sptree  # type: nx.DiGraph
        assert nx.is_tree(sptree)

        next_previous_node = nodes[0]

        # Addresses, not nodes, need to be iterated, because the address
        # associated with a node changes during the execution of the algorithm.

        for logic_addr in nodes.logic_addresses_iter():
            node = nodes.from_logic_address(logic_addr)

            previous_node = next_previous_node
            next_previous_node = node

            while True:
                father, = sptree.predecessors(node)

                if father.logic_address > node.logic_address:
                    node.swap_logic_address(father)
                else:
                    break

            if father == previous_node:
                continue

            try:
                greatest_son = max(sptree.successors_iter(previous_node),
                                   key=lambda x: x.logic_address)
                node.swap_logic_address(greatest_son)
                continue

            except ValueError:
                pass

            try:
                ancestor_of_previous, = sptree.predecessors(previous_node)
            except IndexError:
                continue

            while ancestor_of_previous != 0 and father != ancestor_of_previous:

                greatest_son = max(sptree.successors_iter(ancestor_of_previous),
                                   key=lambda x: x.logic_address)

                if greatest_son.logic_address > node.logic_address:
                    node.swap_logic_address(greatest_son)
                    continue

                ancestor_of_previous, = sptree.predecessors(previous_node)

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
        raise NotImplementedError

    def __update_node_graph(self, dest, packet: ResponsePacket):

        node_graph = self.node_graph
        sptree = self.__shortest_paths_tree
        return_path = nx.shortest_path(sptree, dest, 0, 'weight')

        for source_node, noise_table in zip(return_path, packet.noise_tables):

            for dest_node, noise_level in noise_table.items():

                node_graph[source_node][dest_node]['noise'] = noise_level

        self.__shortest_paths_tree = shortest_paths_tree(node_graph, 0, 'noise')
