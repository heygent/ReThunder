import logging
import itertools
import collections
from typing import List, Dict, Tuple

import networkx as nx
from networkx.algorithms import bipartite
import simpy

from infrastructure.message import make_transmission_delay
from protocol.packet import AddressType
from protocol.packet import Packet, RequestPacket, ResponsePacket
from protocol.rethunder_node import ReThunderNode, ACK_TIMEOUT, RETRANSMISSIONS
from protocol.node_data_manager import NodeDataManager, NodeDataT
from utils.condition_var import BroadcastConditionVar
from utils.func import singledispatchmethod
from utils.preemption_first_resource import PreemptionFirstResource
from utils.run_process_decorator import run_process
from utils.graph import shortest_paths_tree, preorder_tree_dfs

logger = logging.getLogger(__name__)


AnswerPendingRecord = collections.namedtuple(
    'AnswerPendingRecord', 'token, path, send_time, expiry_delay'
)


class BusyError(Exception):
    pass


class MasterNode(ReThunderNode):

    def __init__(self, network, on_message_received):

        super().__init__(network, 0, 0)

        self.node_graph = nx.Graph()    # type: nx.Graph
        self.on_message_received = on_message_received
        self._sptree = None             # type: nx.DiGraph
        self._shortest_paths = None     # type: Dict[NodeDataT, List[NodeDataT]]
        self._free_network_res = PreemptionFirstResource(self.env)
        self._send_cond = BroadcastConditionVar(self.env)
        self._answer_pending = None
        self._node_manager = NodeDataManager()
        self._token_it = itertools.cycle(range(1 << Packet.TOKEN_BIT_SIZE))

    def __repr__(self):
        return '<MasterNode>'

    def init_from_netgraph(self, netgraph: nx.Graph, initial_noise_value=0.5,
                           **kwargs):

        addr_graph = bipartite.projected_graph(
            netgraph, (node for node in netgraph.nodes_iter()
                       if isinstance(node, ReThunderNode))
        )

        # noinspection PyTypeChecker
        nx.relabel_nodes(addr_graph, lambda x: x.static_address, False)

        return self.init_from_static_addr_graph(
            addr_graph, initial_noise_value, **kwargs
        )

    def init_from_static_addr_graph(self, addr_graph, initial_noise_value=0.5,
                                    **kwargs):

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

        assign_logic_addr = kwargs.get('assign_logic_addr', True)

        if not assign_logic_addr:
            return

        addr_iter = itertools.count()

        def assign_logic_address(n: NodeDataT):
            n.logic_address = next(addr_iter)

        preorder_tree_dfs(self._sptree, nodes[0], action=assign_logic_address)

    def _update_sptree(self):
        nodes = self._node_manager

        self._shortest_paths = shortest_paths = nx.shortest_path(
            self.node_graph, nodes[0], weight='noise'
        )

        self._sptree = shortest_paths_tree(shortest_paths)

    def _readdress_nodes(self):

        nodes = self._node_manager

        sptree = self._sptree  # type: nx.DiGraph
        assert nx.is_tree(sptree)

        previous_node_addr = 0

        # Addresses, not nodes, need to be iterated, because the address
        # associated with a node changes during the execution of the algorithm.

        for logic_addr in nodes.logic_addresses_view()[1:]:

            node = nodes.from_logic_address(logic_addr)
            previous_node = nodes.from_logic_address(previous_node_addr)

            previous_node_addr = logic_addr

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

            ancestor_of_previous, = sptree.predecessors(previous_node)

            while (ancestor_of_previous != nodes[0] and
                   ancestor_of_previous != father):

                greatest_son = max(sptree.successors_iter(ancestor_of_previous),
                                   key=lambda x: x.logic_address)

                if greatest_son.logic_address > node.logic_address:
                    node.swap_logic_address(greatest_son)
                    break

                ancestor_of_previous, = sptree.predecessors(
                    ancestor_of_previous
                )

    @run_process
    def send_message_proc(self, message, message_length,
                          destination_static_addr: int, preempt=False):

        env = self.env

        with self._free_network_res.request(preempt) as req:

            yield req
            self._send_cond.broadcast((message, message_length,
                                       destination_static_addr))

            if self._answer_pending is None:
                return

            try:
                yield env.timeout(self._answer_pending.expiring_time - env.now)
                self._answer_pending = None
            except simpy.Interrupt:
                logger.warning(
                    f"{self} request message was preempted before expiry."
                )

    @run_process
    def run_proc(self):

        if self._sptree is None:
            raise ValueError(f"{self} must be initialized before it's started.")

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

                msg, msg_len, dest_addr = send_ev.value
                dest = self._node_manager[dest_addr]
                path_to_dest = self._shortest_paths[dest]

                packet = self._make_request_packet(msg, msg_len, path_to_dest)
                self._send_to_network_proc(packet, packet.number_of_frames())

                estimated_rtt = (
                    len(path_to_dest) *
                    ACK_TIMEOUT *
                    RETRANSMISSIONS *
                    make_transmission_delay(self._transmission_speed,
                                            packet.number_of_frames())
                ) // 2

                self._answer_pending = AnswerPendingRecord(
                    packet.token, path_to_dest,
                    expiring_time=self.env.now + estimated_rtt
                )

            if recv_ev.processed:
                self._handle_received(recv_ev.value)

    @singledispatchmethod
    def _handle_received(self, _):
        logger.error(f'{self} received something unsupported.')

    @_handle_received.register(Packet)
    def _(self, packet):
        logger.warning(f'{self} received {packet}, which cannot be handled.')

    @_handle_received.register(RequestPacket)
    def _(self, _):
        logger.warning(f'{self} received a RequestPacket.')

    @_handle_received.register(ResponsePacket)
    def _(self, packet):

        answer_pending = self._answer_pending

        if answer_pending.token != packet.token:
            logger.warning(
                f'{self} has received an answer with token '
                f'{packet.token}. Current token is {answer_pending.token}, '
                'ignoring'
            )
            return

        logger.debug(f"{self} received answer to token {packet.token}")

        self._update_node_graph(packet)
        self._update_sptree()
        self._readdress_nodes()

        self.on_message_received(self, packet.payload, packet.payload_length)
        self._answer_pending = None

    def _make_request_packet(self, message, length, path_to_dest):

        node_graph = self.node_graph

        packet = RequestPacket()
        packet.payload = message
        packet.payload_length = length

        destination_addr = path_to_dest[-1].logic_address

        path = []           # type: List[Tuple[AddressType, int]]
        new_addrs = {}      # type: Dict[int, int]

        next_static_addressing_used = True

        for next_node, node in zip(path_to_dest[::-1], path_to_dest[-2::-1]):

            static_addressing_used = next_static_addressing_used
            next_static_addressing_used = False

            if next_node.current_logic_address is None:

                new_addrs[next_node.static_address] = next_node.logic_address
                path.append((AddressType.static, next_node.static_address))

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

            if ambiguous_addressing:
                path.append((AddressType.static, next_node.static_address))

                destination_addr = next_node.current_logic_address
                next_static_addressing_used = True

            elif wrong_addressing or static_addressing_used:
                destination_addr = next_node.current_logic_address
                path.append((AddressType.logic, destination_addr))

            if next_node.logic_address != next_node.current_logic_address:
                new_addrs[next_node.static_address] = next_node.logic_address

        packet = RequestPacket()
        packet.token = next(self._token_it)

        packet.source_static = self.static_address
        packet.source_logic = self.logic_address

        dest_type, dest = path.pop()

        packet.destination = dest
        packet.code_is_addressing_static = dest_type is AddressType.static

        next_hop = path_to_dest[1]
        packet.next_hop = next_hop.static_address

        packet.code_destination_is_endpoint = len(path) == 0

        packet.payload = message
        packet.payload_length = length

        packet.path = path
        packet.new_logic_addresses = new_addrs

        return packet

    def _update_node_graph(self, packet: ResponsePacket):

        node_graph = self.node_graph
        message_path = self._answer_pending.path

        for node in message_path:
            node.current_logic_address = node.logic_address

        for source_node, noise_table in zip(reversed(message_path),
                                            packet.noise_tables):

            for dest_node, noise_level in noise_table.items():

                node_graph[source_node][dest_node]['noise'] = noise_level
