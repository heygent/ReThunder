import logging
import unittest

import networkx as nx

from infrastructure import Bus
from infrastructure import Network
from protocol import MasterNode
from protocol import SlaveNode


class TestProtocol(unittest.TestCase):

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

    def test_tree(self):
        network = self.network

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
                  for i in range(1, 19)]

        buses = [Bus(network, 10) for _ in range(2)]

        for bus, n1, n2 in zip(buses, slaves, slaves[1:]):
            network.netgraph.add_star((bus, n1, n2))

