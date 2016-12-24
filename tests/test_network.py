import unittest

import simpy

from infrastructure.bus import Bus
from infrastructure.message import CollisionSentinel
from infrastructure.network import Network
from nodes.nodes import SenderNode, ReceiverNode


class TestNetwork(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.network = Network(transmission_speed=2)
        self.prop_delay = 1

    def test_reception(self):

        network = self.network
        prop_delay = self.prop_delay
        messages = [('Message{}'.format(i), 8) for i in range(10)]

        sender = SenderNode(network)
        receiver = ReceiverNode(network)
        bus = Bus(network, prop_delay)

        for node in (sender, receiver):
            network.netgraph.add_edge(node, bus)

        processes = [node.run_proc() for node in (sender, receiver)]

        network.env.run()

        self.assertEqual(receiver.received,
                         [(6 * i, msg) for i, (msg, _) in enumerate(messages,
                                                                    start=1)])

    def test_collisions(self):

        network = self.network
        messages = [('Message{}'.format(i), 8) for i in range(10)]
        prop_delay = self.prop_delay

        senders = [SenderNode(network, messages) for _ in range(2)]
        receiver = ReceiverNode(network)
        nodes = (*senders, receiver)

        bus = Bus(network, prop_delay)

        for node in nodes:
            network.netgraph.add_edge(node, bus)

        processes = [node.run_proc() for node in nodes]

        network.env.run()

        self.assertEqual(receiver.received,
                         [(6 * i, CollisionSentinel)
                          for i, (msg, _) in enumerate(messages, start=1)])

