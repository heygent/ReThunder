
import unittest

import simpy

from infrastructure.bus import Bus
from nodes.nodes import SenderNode, ReceiverNode


class TestNetwork(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_reception(self):

        env = simpy.Environment()
        messages = [('Message{}'.format(i), 8) for i in range(10)]
        trans_speed = 2
        prop_delay = 1

        sender = SenderNode(env, trans_speed, messages)
        receiver = ReceiverNode(env, trans_speed)

        bus = Bus(env, prop_delay)

        for node in (sender, receiver):
            bus.register_node(node)

        processes = [node.run_proc() for node in (sender, receiver)]

        env.run()

        self.assertEqual(receiver.received,
                         [(6 * i, msg) for i, (msg, _) in enumerate(messages,
                                                                    start=1)])

    def test_collisions(self):

        env = simpy.Environment()
        messages = [('Message{}'.format(i), 8) for i in range(10)]
        trans_speed = 2
        prop_delay = 1

        senders = [SenderNode(env, trans_speed, messages) for _ in range(2)]
        receiver = ReceiverNode(env, trans_speed)
        nodes = [*senders, receiver]

        bus = Bus(env, prop_delay)

        for node in nodes:
            bus.register_node(node)

        processes = [node.run_proc() for node in nodes]

        env.run()

        self.assertEqual(receiver.received,
                         [(6 * i, msg) for i, (msg, _) in enumerate(messages,
                                                                    start=1)])




