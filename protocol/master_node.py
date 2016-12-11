import logging
import itertools
from typing import List, Dict

import networkx as nx
import simpy

from protocol.packet import (
    ResponsePacket, RequestPacket, HelloRequestPacket, HelloResponsePacket
)
from protocol.application import Application
from protocol.rethunder_node import ReThunderNode
from protocol.node_data_manager import NodeDataManager, NodeDataT
from protocol.tracer import Tracer
from utils.condition_var import BroadcastConditionVar
from utils.iterblocks import iterblocks
from utils.run_process_decorator import run_process
from utils.graph import shortest_paths_tree, preorder_tree_dfs

logger = logging.getLogger(__name__)


class BusyError(Exception):
    pass


class MasterNode(ReThunderNode):

    def __init__(self, env, transmission_speed, application):

        super().__init__(env, transmission_speed, 0, 0)

        self.node_graph = nx.Graph()    # type: nx.Graph
        self.application = application  # type: Application
        self._sptree = None            # type: nx.DiGraph
        self._shortest_paths = None    # type: Dict[NodeDataT, List[NodeDataT]]
        self._send_cond = BroadcastConditionVar(self.env)
        self._current_message = None
        self._current_message_path = None
        self._node_manager = NodeDataManager()

    def __repr__(self):
        return '<MasterNode>'

    def init_from_static_addr_graph(self, addr_graph, initial_noise_value=0.5):

        if not 0 <= initial_noise_value <= 2:
            raise ValueError('initial_noise_value must be between 0 and 2')

        nodes = self._node_manager

        # nx.relabel_nodes accepts a function for relabeling nodes.
        # It is poorly documented though, to the point that the type checker
        # fires warnings if you do.

        # noinspection PyTypeChecker
        node_graph = nx.relabel_nodes(addr_graph, nodes.create, copy=True)

        # Same here. Normally set_edge_attributes takes a dict as its last
        # argument, but other types are supported (see networkx doc).

        # noinspection PyTypeChecker
        nx.set_edge_attributes(node_graph, 'noise', initial_noise_value)

        self.node_graph = node_graph
        self._update_sptree()

        addr_iter = itertools.count()

        def assign_logic_address(n: NodeDataT):
            n.logic_address = next(addr_iter)

        preorder_tree_dfs(self._sptree, nodes[0], action=assign_logic_address)

    def _update_sptree(self):
        nodes = self._node_manager

        shortest_paths = nx.shortest_path(self.node_graph, nodes[0], 'noise')
        self._sptree = shortest_paths_tree(shortest_paths)
        self._shortest_paths = shortest_paths

    def _readdress_nodes(self):

        nodes = self._node_manager

        sptree = self._sptree  # type: nx.DiGraph
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
                    node = father
                else:
                    break

            father, = sptree.predecessors(node)
            if father == previous_node:
                continue

            greatest_son = max(sptree.successors_iter(previous_node),
                               key=lambda x: x.logic_address, default=None)

            if greatest_son is not None:
                node.swap_logic_address(greatest_son)
                continue

            try:
                ancestor_of_previous, = sptree.predecessors(previous_node)
            except IndexError:
                continue

            while (ancestor_of_previous != nodes[0] and
                   father != ancestor_of_previous):

                greatest_son = max(sptree.successors_iter(ancestor_of_previous),
                                   key=lambda x: x.logic_address)

                if greatest_son.logic_address > node.logic_address:
                    node.swap_logic_address(greatest_son)
                    node = greatest_son
                    continue

                ancestor_of_previous, = sptree.predecessors(previous_node)

    def send_message(self, message, message_length,
                     destination_static_addr: int):

        if self._current_message is not None:
            raise BusyError("{} is waiting for another message "
                            "response.".format(self))

        self._send_cond.broadcast((message, message_length,
                                   destination_static_addr))

    @run_process
    def run(self):

        if self._sptree is None:
            raise ValueError("{} must be initialized before it's started.")

        env = self.env

        while True:

            send_ev = self._send_cond.wait()      # type: simpy.Event
            recv_ev = self._receive_packet_proc()  # type: simpy.Event

            events = (send_ev, recv_ev)

            yield env.any_of(events)

            # if the events happen at the same time unit, let them all be
            # processed before proceeding
            yield env.timeout(0)

            assert any(e.processed for e in events), "Spurious wake"

            if send_ev.processed:

                assert self._current_message is None, (
                    "{} has not been prevented to send a message while "
                    "waiting for a response, so it is in an invalid state."
                    .format(self))

                packet = self._make_request_packet(*send_ev.value)
                self._send_to_network_proc(packet, packet.number_of_frames())

            if recv_ev.processed:

                packet = recv_ev.value

                if isinstance(packet, RequestPacket):
                    pass

                elif isinstance(packet, ResponsePacket):

                    self._update_node_graph(packet)
                    self._update_sptree()
                    self._readdress_nodes()

                    self.application.message_received(packet.payload,
                                                      packet.payload_length)
                elif isinstance(packet,
                                (HelloRequestPacket, HelloResponsePacket)):
                    logger.warning(
                        '{} received a hello message, which cannot be handled.'
                        .format(self)
                    )
                else:
                    logger.error(
                        '{} received something unsupported.'
                        .format(self), extra={'received': packet}
                    )

    def _make_request_packet(self, message, length, destination_addr):

        nodes = self._node_manager
        node_graph = self.node_graph

        final_destination = nodes[destination_addr]
        shortest_path = self._shortest_paths[final_destination]

        packet = RequestPacket()
        packet.payload = message
        packet.payload_length = length

        destination_addr = final_destination.logic_address
        address_stack = []           # type: List[int]
        tracer_stack = []            # type: List[Tracer]

        next_static_addressing_used = True

        for next_node, node in iterblocks(reversed(shortest_path), 2, 1):

            static_addressing_used = next_static_addressing_used
            next_static_addressing_used = False

            if next_node.current_logic_address == -1:

                address_stack.append(next_node.static_address)
                address_stack.append(next_node.logic_address)

                tracer_stack.append(
                    Tracer(static_addressing=True, new_address=True)
                )

                destination_addr = next_node.logic_address
                next_static_addressing_used = True

                continue

            neighbors = node_graph.neighbors(node)

            max_address = max(c.current_logic_address for c in neighbors
                              if c.current_logic_address <= destination_addr)

            wrong_addressing = max_address != next_node.current_logic_address

            candidates = [
                c for c in neighbors
                if c.current_logic_address == next_node.current_logic_address
            ]

            ambiguous_addressing = len(candidates) > 1

            tracer = Tracer()

            if ambiguous_addressing:
                tracer.static_addressing = True
                address_stack.append(next_node.static_address)

                destination_addr = next_node.current_logic_address
                next_static_addressing_used = True

            elif wrong_addressing:
                address_stack.append(next_node.current_logic_address)

                destination_addr = next_node.current_logic_address
                next_static_addressing_used = True

            else:
                if static_addressing_used:
                    address_stack.append(next_node.current_logic_address)

                    destination_addr = next_node.current_logic_address

            if next_node.logic_address != next_node.current_logic_address:
                tracer.new_address = True
                address_stack.append(next_node.logic_address)

            if tracer.is_valid():
                tracer_stack.append(tracer)
            else:
                tracer_stack[-1].offset += 1

        packet = RequestPacket()

        if tracer_stack[-1].offset == 0:
            tracer = tracer_stack.pop()
        else:
            tracer_stack[-1].offset -= 1
            tracer = Tracer()

        packet.source_static = self.static_address
        packet.source_logic = self.logic_address

        if tracer.new_address:
            packet.code_has_new_logic_addr = True
            packet.new_logic_addr = address_stack.pop()

        packet.code_is_addressing_static = tracer.static_addressing
        packet.destination = address_stack.pop()

        packet.payload = message
        packet.payload_length = length

        packet.path = address_stack
        packet.tracers_list = tracer_stack

        return packet

    def _update_node_graph(self, packet: ResponsePacket):

        node_graph = self.node_graph
        message_path = self._current_message_path

        for node in message_path:
            node.current_logic_address = node.logic_address

        for source_node, noise_table in zip(reversed(message_path),
                                            packet.noise_tables):

            for dest_node, noise_level in noise_table.items():

                node_graph[source_node][dest_node]['noise'] = noise_level
