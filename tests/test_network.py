import unittest

import simpy

from infrastructure.bus import Bus
from infrastructure.network_interface import NetworkNode
from utils.iterblocks import iterblocks


class TestNetwork(unittest.TestCase):

    def test1(self):

        env = simpy.Environment()
        prop_delay = 1
        trans_speed = 1

        node_interfaces = [NetworkNode(env, trans_speed) for _ in range(4)]
        buses = []

        msg = "I'm Hannibal"
        msg_len = 4

        for node_group in iterblocks(node_interfaces, 2, 1):

            bus = Bus(env, prop_delay)

            for node in node_group:
                bus.register_node(node)

            buses.append(bus)

        # noinspection PyShadowingNames
        def send_to_network(env, node: NetworkNode, delay, msg, msg_len):
            yield env.timeout(delay)
            env.process(node._send_to_network_proc(msg, msg_len))

        for i, node in enumerate(node_interfaces):
            env.process(send_to_network(env, node, 10 * i, msg, msg_len))

        env.run()

        pass








