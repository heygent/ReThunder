import collections
import itertools
import logging
from typing import List, Dict, Tuple

import networkx as nx
import simpy
from networkx.algorithms import bipartite

from infrastructure import Bus
from infrastructure.message import make_transmission_delay
from protocol.node_data_manager import NodeDataManager, NodeDataT
from protocol.packet import AddressType
from protocol.packet import Packet, RequestPacket, ResponsePacket
from protocol.rethunder_node import ReThunderNode
from utils.func import singledispatchmethod
from utils.graph import shortest_paths_tree, preorder_tree_dfs
from utils.simpy_process import simpy_process

logger = logging.getLogger(__name__)


AnswerPendingRecord = collections.namedtuple(
    'AnswerPendingRecord',
    'token, path, new_addrs_table, send_time, expiry_delay'
)

AnswerPendingRecord.expiry_time = property(
    lambda self: self.send_time + self.expiry_delay
)

PAST_NOISE_HISTORY_WEIGHT = 2/3


class MasterNode(ReThunderNode):

    def __init__(self, network, on_message_received=None):

        super().__init__(network, 0, 0)

        self.node_graph = nx.DiGraph()
        self.sent_messagges = []
        self.on_message_received = on_message_received
        self._sptree: nx.DiGraph = None
        self._shortest_paths: Dict[NodeDataT, List[NodeDataT]] = None
        self._send_store = simpy.Store(self.env)
        self._answer_pending = None
        self._node_manager = NodeDataManager()
        self._token_it = itertools.cycle(range(1 << Packet.TOKEN_BIT_SIZE))

    def __repr__(self):
        return '<MasterNode>'

    def init_from_netgraph(self, netgraph: nx.Graph, initial_noise_value=0.5,
                           **kwargs):

        bus_graph = any(isinstance(node, Bus) for node in netgraph.nodes_iter())

        if bus_graph:
            addr_graph: nx.Graph = bipartite.projected_graph(
                netgraph, [node for node in netgraph.nodes_iter()
                           if isinstance(node, ReThunderNode)]
            )
        else:
            addr_graph: nx.Graph = netgraph.copy()

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

        mappings = {addr: nodes.create(addr)
                    for addr in sorted(addr_graph.nodes())}

        node_graph = nx.relabel_nodes(addr_graph, mappings, copy=True)

        # Normally set_edge_attributes takes a dict as its last argument,
        # but other types are supported (see networkx doc).

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

    def _update_noise_table(self, packet: Packet):
        super()._update_noise_table(packet)
        self._update_node_graph_from_table(self._node_manager[0],
                                           self.noise_table)
        self._update_sptree()
        self._readdress_nodes()

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

    def send_message(self, message, message_length, dest_static_addr):
        self._send_store.put((message, message_length, dest_static_addr))

    @simpy_process
    def run_proc(self):

        if self._sptree is None:
            raise ValueError(f"{self} must be initialized before it's started.")

        send_ev = None

        logger.info(f"{self} started.")

        while True:

            send_ev = send_ev or self._send_store.get()
            recv_ev = self._receive_packet_ev()

            cond_value = yield send_ev | recv_ev

            if recv_ev in cond_value:
                self._handle_received(recv_ev.value)

            elif send_ev in cond_value:
                self._answer_pending = yield from self._handle_send_request(
                    send_ev.value
                )
                yield from self._wait_for_answer()
                send_ev = None

    def _handle_send_request(self, msg_data):

        msg, msg_len, dest_addr = msg_data

        try:
            dest = self._node_manager[dest_addr]
        except KeyError:
            raise ValueError(f"{self} is not aware of a node with address "
                             f"{dest_addr}")

        path_to_dest = self._shortest_paths[dest]

        packet = self._make_request_packet(msg, msg_len, path_to_dest)

        self.sent_messagges.append(msg)
        logger.info(f"Master sends request with token {packet.token}")

        yield self._transmit_process(packet, packet.number_of_frames())

        estimated_rtt = (
            len(path_to_dest) *
            make_transmission_delay(self._transmission_speed,
                                    packet.number_of_frames())
            + 50
        ) * 5

        return AnswerPendingRecord(
            packet.token, path_to_dest, packet.new_logic_addresses,
            self.env.now, estimated_rtt
        )

    def _wait_for_answer(self):
        pending = self._answer_pending
        to = self.env.timeout(pending.expiry_delay)
        recv_ev = None

        while True:
            recv_ev = recv_ev or self._receive_packet_ev()
            cond_value = yield recv_ev | to

            if to in cond_value:
                logger.info(f"Timeout for answer with token {pending.token}")
                self._unset_ambiguous_addresses(pending.new_addrs_table)
                break
            elif recv_ev in cond_value:
                self._handle_received(recv_ev.value)

                if self._waiting_for_answer():
                    recv_ev = None
                else:
                    break

    @singledispatchmethod
    def _handle_received(self, _):
        logger.error(f'{self} received something unsupported.')

    @_handle_received.register(Packet)
    def _(self, packet):
        logger.warning(f'{self} received {packet}, which cannot be handled.')

    @_handle_received.register(RequestPacket)
    def _(self, _):
        logger.info(f'{self} received a RequestPacket.')

    @_handle_received.register(ResponsePacket)
    def _(self, packet):

        if packet.next_hop != self.static_address:
            return

        pending = self._answer_pending

        tok = None if pending is None else pending.token

        if tok != packet.token:
            logger.warning(
                f'{self} has received an answer with token '
                f'{packet.token}. Current token is {tok}, ignoring'
            )
            return

        logger.debug(f"{self} received answer to token {packet.token}")

        self._update_node_graph_from_packet(packet)
        self._update_sptree()
        self._readdress_nodes()

        msg_callback = self.on_message_received or (lambda x, y, z: None)
        msg_callback(self, packet.payload, packet.payload_length)

        self._answer_pending = None

    def _make_request_packet(self, message, length, path_to_dest) \
            -> RequestPacket:

        node_graph = self.node_graph

        packet = RequestPacket()
        packet.payload = message
        packet.payload_length = length

        destination_addr = path_to_dest[-1].logic_address

        path: List[Tuple[AddressType, int]] = []
        new_addrs: Dict[int, int] = {}

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
                              if c.current_logic_address is not None
                              and c.current_logic_address <= destination_addr)

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

        packet.payload = message
        packet.payload_length = length

        packet.path = path
        packet.new_logic_addresses = new_addrs

        return packet

    def _unset_ambiguous_addresses(self, new_addrs_table):

        nodes = self._node_manager

        for static_addr in new_addrs_table.keys():
            nodes[static_addr].current_logic_address = None

    def _update_node_graph_from_packet(self, packet: ResponsePacket):

        nodes = self._node_manager
        new_addresses = self._answer_pending.new_addrs_table
        message_path = self._answer_pending.path

        for static_addr, new_logic_addr in new_addresses.items():
            nodes[static_addr].current_logic_address = new_logic_addr

        for source_node, noise_table in zip(message_path[1:],
                                            reversed(packet.noise_tables)):

            self._update_node_graph_from_table(source_node, noise_table)

    def _update_node_graph_from_table(self, source, table):

        graph = self.node_graph
        node_manager = self._node_manager

        for dest_addr, new_noise in table.items():
            dest = node_manager[dest_addr]
            try:
                old_noise = graph[source][dest]['noise']
                graph[source][dest]['noise'] = (
                    old_noise * PAST_NOISE_HISTORY_WEIGHT +
                    new_noise * (1 - PAST_NOISE_HISTORY_WEIGHT)
                )
            except KeyError:
                graph.add_edge(source, dest, dict(noise=new_noise))

    def _waiting_for_answer(self):
        pending: AnswerPendingRecord = self._answer_pending

        return pending is not None and pending.expiry_time >= self.env.now
