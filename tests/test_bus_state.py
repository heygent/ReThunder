import unittest

import simpy

from infrastructure.bus import BusState
from infrastructure.message import TransmittedMessage, CollisionSentinel


def occupy_proc(env, bs, msg, delay):
    yield env.timeout(delay)
    bs.occupy(msg)


def receiver_proc(env: simpy.Environment, busstate, output_received_list):

    while True:
        message = yield busstate.receive_current_transmission_ev()
        output_received_list.append((env.now, message))


class BusStateTest(unittest.TestCase):

    def test_single_send(self):

        env = simpy.Environment()
        bs = BusState(env, 5)

        message = TransmittedMessage('Message1', 1000)
        received_messages = []

        bs.occupy(message)
        env.process(receiver_proc(env, bs, received_messages))
        env.run()

        self.assertEqual(received_messages, [(5, message)])

    def test_collision(self):

        env = simpy.Environment()
        bs = BusState(env, 5)

        messages = [TransmittedMessage('Message{}'.format(i), 1000) for i in range(4)]
        received_messages = []

        for msg in messages:
            bs.occupy(msg)

        env.process(receiver_proc(env, bs, received_messages))
        env.run()

        self.assertEqual(received_messages,
                         [(5, TransmittedMessage(CollisionSentinel, 1000))])

    def test_multiple_collisions(self):

        env = simpy.Environment()
        bs = BusState(env, 5)

        messages = [TransmittedMessage('Message{}'.format(i), 1000) for i in range(5)]
        received_messages = []

        for i, msg in enumerate(messages):
            env.process(occupy_proc(env, bs, msg, i))

        env.process(receiver_proc(env, bs, received_messages))
        env.run()

        self.assertEqual(received_messages,
                         [(5, TransmittedMessage(CollisionSentinel, 1004))])

    def test_consecutive_sends(self):

        env = simpy.Environment()
        bs = BusState(env, 5)

        messages = [TransmittedMessage('Message{}'.format(i), 1000)
                    for i in range(3)]

        received_messages = []

        for i, msg in enumerate(messages):
            env.process(occupy_proc(env, bs, msg, i * 5))

        env.process(receiver_proc(env, bs, received_messages))
        env.run()

        self.assertEqual(received_messages,
                         [(i * 5, msg) for i, msg in enumerate(messages,
                                                               start=1)])
