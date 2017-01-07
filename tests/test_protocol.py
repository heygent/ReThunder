import unittest

import networkx as nx

from infrastructure import Bus
from infrastructure import Network
from protocol import MasterNode
from protocol import SlaveNode
import logging


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
        master = MasterNode(network)
        bus = Bus(network, 20)

        msg = "Blip"
        ans = "Blop"

        slaves = [
            SlaveNode(network, i, on_message_received=lambda x, y, z: (ans, 4))
            for i in range(1, 3)
        ]

        for node in (master, *slaves):
            network.netgraph.add_edge(bus, node)

        master.init_from_static_addr_graph(nx.star_graph(3))
        network.run_nodes_processes()

        master.send_message(msg, 4, dest_static_addr=1)
        master.send_message(msg, 4, dest_static_addr=2)
        network.env.run()

