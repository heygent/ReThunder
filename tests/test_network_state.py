import unittest

import simpy

from infrastructure.message import (
    TransmittedMessage, make_transmission_delay, CollisionSentinel
)
from infrastructure.node import NetworkState


def receiver_proc(env: simpy.Environment, netstate: NetworkState,
                  output_received_list):

    while True:
        message = yield netstate.receive_current_transmission_ev()
        output_received_list.append((env.now, message))


def schedule_proc(env: simpy.Environment, fn, delay=0):
    yield env.timeout(delay)
    fn()


class TestNetworkState(unittest.TestCase):

    def setUp(self):

        self.env = simpy.Environment()
        self.netstate = NetworkState(self.env)

    def test_single_send(self):

        bps = 8
        val = 'A' * 20

        message = TransmittedMessage(val, make_transmission_delay(bps, 20))

        env = self.env
        netstate = self.netstate

        received_list = []
        env.process(receiver_proc(env, netstate, received_list))
        netstate.occupy(message)

        env.run()
        self.assertEqual(received_list, [(message.transmission_delay, message)])

    def test_collision(self):

        message1 = TransmittedMessage('Message1', 20)
        message2 = TransmittedMessage('Message2', 50)

        env = self.env
        netstate = self.netstate

        received_list = []
        env.process(receiver_proc(env, netstate, received_list))
        netstate.occupy(message1)
        env.process(schedule_proc(env, lambda: netstate.occupy(message2), 10))

        env.run()
        self.assertEqual(received_list,
                         [(60, TransmittedMessage(CollisionSentinel, 60))])

    def test_immediate_consecutive_sends(self):

        messages = [TransmittedMessage('Message1', 20),
                    TransmittedMessage('Message2', 50)]

        env = self.env
        netstate = self.netstate

        received_list = []
        env.process(receiver_proc(env, netstate, received_list))
        netstate.occupy(messages[0])
        env.process(schedule_proc(env, lambda: netstate.occupy(messages[1]),
                                  20))

        env.run()
        self.assertEqual(received_list,
                         [(i, msg) for i, msg in zip([20, 70], messages)])

    def test_multiple_collisions(self):

        messages = [TransmittedMessage('Message{}'.format(i), 10)
                    for i in range(1, 11)]

        env = self.env
        netstate = self.netstate

        received_list = []
        env.process(receiver_proc(env, netstate, received_list))

        def occupy_process(msg, delay):
            yield env.timeout(delay)
            netstate.occupy(msg)

        for message in messages:
            env.process(occupy_process(message, 10))

        env.run()

        self.assertEqual(received_list,
                         [(20, TransmittedMessage(CollisionSentinel, 10))])

    def test_multiple_collisions_with_different_trans_delays(self):

        messages = [TransmittedMessage('Message{}'.format(i), 10 + i)
                    for i in range(1, 11)]

        env = self.env
        netstate = self.netstate

        received_list = []
        env.process(receiver_proc(env, netstate, received_list))

        def occupy_process(msg, delay):
            yield env.timeout(delay)
            netstate.occupy(msg)

        for message in messages:
            env.process(occupy_process(message, 10))

        env.run()

        self.assertEqual(received_list,
                         [(30, TransmittedMessage(CollisionSentinel, 20))])

    def test_multiple_consecutive_collisions(self):

        messages = [TransmittedMessage('Message{}'.format(i), 10)
                    for i in range(1, 11)]

        env = self.env
        netstate = self.netstate

        received_list = []
        env.process(receiver_proc(env, netstate, received_list))

        def occupy_process(msg, delay):
            yield env.timeout(delay)
            netstate.occupy(msg)

        for i, message in enumerate(messages):
            env.process(occupy_process(message, 10 + i))

        env.run()

        self.assertEqual(received_list,
                         [(29, TransmittedMessage(CollisionSentinel, 19))])
