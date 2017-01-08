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

        master.init_from_static_addr_graph(nx.path_graph(2))
        network.netgraph.add_path((master, bus, slave))

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

        master.init_from_static_addr_graph(nx.star_graph(50))
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

        for n1, n2 in zip((master, *slaves), slaves):
            bus = Bus(network, 10)
            network.netgraph.add_path((n1, bus, n2))

        master.init_from_static_addr_graph(nx.path_graph(21))
        network.run_nodes_processes()
        master.send_message(msg, len(msg), 20)
        network.env.run()

        self.assertEquals(received, ["Blop_20"])
