import logging
import random
import unittest

from itertools import combinations
import networkx as nx

from infrastructure import Bus
from infrastructure import Network
from protocol import MasterNode
from protocol import SlaveNode


class SimpleTestProtocol(unittest.TestCase):

    def setUp(self):
        self.network = network = Network(transmission_speed=0.5)
        network.configure_root_logger(level=logging.DEBUG)

    def test_one_slave(self):

        network = self.network
        received = []

        master = MasterNode(
            network, on_message_received=lambda _, m, __: received.append(m)
        )

        bus = Bus(network, 20)

        msg = "Hallo, brothers and sistas!"
        ans = "Hallo to you, sir!"

        slave = SlaveNode(network, 1,
                          on_message_received=lambda x, y, z: (ans, len(ans)))

        network.netgraph.add_path((master, bus, slave))
        master.init_from_netgraph(network.netgraph)

        network.run_nodes_processes()
        master.send_message(msg, len(msg), slave.static_address)
        network.env.run()

        self.assertEqual(received, [ans])

    def test_many_slaves(self):

        network = self.network
        bus = Bus(network, 20)
        received = []
        master = MasterNode(
            network, on_message_received=lambda _, m, __: received.append(m)
        )

        msg = "Blip"
        ans = "Blop_{0}"

        def slave_on_received(slave, msg, msg_len):
            res = ans.format(slave.static_address)
            return res, len(res)

        slaves = [
            SlaveNode(network, i, on_message_received=slave_on_received)
            for i in range(1, 51)
        ]

        for node in (master, *slaves):
            network.netgraph.add_edge(bus, node)

        master.init_from_netgraph(network.netgraph)
        network.run_nodes_processes()

        for addr in range(1, 51):
            master.send_message(msg, 4, addr)

        network.env.run()

        self.assertEquals(received, [ans.format(addr)
                                     for addr in range(1, 51)])

    def test_line(self):

        network = self.network
        received = []
        master = MasterNode(
            network, on_message_received=lambda _, m, __: received.append(m)
        )

        msg = "Blip"
        ans = "Blop_{0}"

        def slave_on_received(slave, msg, msg_len):
            res = ans.format(slave.static_address)
            return res, len(res)

        slaves = [SlaveNode(network, i, on_message_received=slave_on_received)
                  for i in range(1, 21)]

        network.netgraph.add_path((master, *slaves), propagation_delay=20)
        network.make_buses()
        master.init_from_netgraph(network.netgraph)
        network.run_nodes_processes()

        for addr in range(15, 21):
            master.send_message(msg, len(msg), addr)

        network.env.run()

        self.assertEquals(received, [ans.format(i) for i in range(15, 21)])


class TestTreeConfiguration(unittest.TestCase):

    def setUp(self):
        self.network = network = Network(transmission_speed=0.5)
        network.configure_root_logger(level=logging.DEBUG)

        self.received = received = []
        master = MasterNode(
            network, on_message_received=lambda _, m, __: received.append(m)
        )

        self.msg = msg = "Blip"
        self.ans = ans = "Blop_{0}"

        def slave_on_received(slave, msg, msg_len):
            res = ans.format(slave.static_address)
            return res, len(res)

        self.nodes = nodes = [master]

        # noinspection PyTypeChecker
        nodes.extend(
            SlaveNode(network, i, on_message_received=slave_on_received)
            for i in range(1, 18)
        )

        network.netgraph.add_path(nodes[:3])

        network.netgraph.add_edges_from(combinations(nodes[2:6], 2))
        network.netgraph.add_edges_from(combinations(nodes[6:10], 2))
        network.netgraph.add_edges_from(combinations(nodes[10:14], 2))
        network.netgraph.add_edges_from(combinations(nodes[14:18], 2))

        network.netgraph.add_edge(nodes[3], nodes[6])
        network.netgraph.add_edge(nodes[4], nodes[10])
        network.netgraph.add_edge(nodes[5], nodes[14])

        network.make_buses()

    def test_1(self):

        network = self.network
        nodes = self.nodes
        last_addr = len(nodes) - 1
        msg = self.msg
        ans = self.ans

        nodes[0].init_from_netgraph(network.netgraph)
        network.run_nodes_processes()

        for _ in range(2):
            for i in range(last_addr, 0, -1):
                nodes[0].send_message(msg, len(msg), i)

        network.env.run()

        self.assertEquals(self.received,
                          [ans.format(i) for i in range(last_addr, 0, -1)] * 2)

    def test_random_order(self):
        network = self.network
        nodes = self.nodes
        last_addr = len(nodes) - 1
        msg = self.msg
        ans = self.ans

        should_have_received = []

        nodes[0].init_from_netgraph(network.netgraph)
        network.run_nodes_processes()

        for _ in range(2):
            addr_pool = list(range(last_addr, 0, -1))
            random.shuffle(addr_pool)
            for _ in range(len(nodes) - 1):
                address = addr_pool.pop()
                nodes[0].send_message(msg, len(msg), address)
                should_have_received.append(ans.format(address))

        network.env.run()

        self.assertEquals(self.received, should_have_received)

    def test_with_cycle(self):

        network = self.network
        nodes = self.nodes
        last_addr = len(nodes) - 1
        msg = self.msg
        ans = self.ans

        network.netgraph.add_star((Bus(network, 10), nodes[0], nodes[12]))

        nodes[0].init_from_netgraph(network.netgraph)
        network.run_nodes_processes()

        for _ in range(2):
            for i in range(last_addr, 0, -1):
                nodes[0].send_message(msg, len(msg), i)

        network.env.run()

        self.assertEquals(self.received,
                          [ans.format(i) for i in range(last_addr, 0, -1)] * 2)
