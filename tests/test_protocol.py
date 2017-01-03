import unittest

import networkx as nx

from infrastructure import Bus
from infrastructure import Network
from protocol import MasterNode
from protocol import SlaveNode
import logging


class TestProtocol(unittest.TestCase):

    def master_on_received(self, node, msg, msg_len):
        self.received_by_master.append((self.env.now, msg))

    def setUp(self):

        self.network = network = Network()
        self.env = network.env
        self.master = MasterNode(network, self.master_on_received)
        self.received_by_master = []
        self.master_bus = Bus(network, 20)
        network.netgraph.add_edge(self.master, self.master_bus)

    def test_one_slave(self):

        network = self.network
        master = self.master
        master_bus = self.master_bus

        msg = "Hallo, brothers and sistas!"
        ans = "Hallo to you, sir!"

        slave = SlaveNode(self.network, 1,
                          on_message_received=lambda x, y, z: (ans, len(ans)))

        master.init_from_static_addr_graph(nx.path_graph(2))
        network.netgraph.add_edge(master_bus, slave)

        logging.basicConfig(level=logging.DEBUG)

        for handler in logging.getLogger().handlers:
            network.configure_log_handler(handler)

        network.run_nodes_processes()
        network.env.run()
        master.send_message_proc(msg, len(msg), slave.static_address)
        network.env.run()

        received = self.received_by_master
        pass
