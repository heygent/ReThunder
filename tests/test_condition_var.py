import unittest

import simpy

from utils.condition_var import ConditionVar, BroadcastConditionVar


def waiter(env, condition):
    yield condition.wait()
    return env.now


def signaler(env, signal_fn, interval: int, until=lambda: False):

    while not until():
        yield env.timeout(interval)
        signal_fn()


class TestConditionVar(unittest.TestCase):

    def test_signal(self):

        env = simpy.Environment()
        bell_has_ringed = ConditionVar(env)
        ring_interval = 5
        workers = 5

        worker_procs = [env.process(waiter(env, bell_has_ringed))
                        for _ in range(workers)]

        env.process(
            signaler(env, lambda: bell_has_ringed.signal(),
                     ring_interval, lambda: env.now == 25)
        )

        env.run()

        self.assertListEqual(
            [5 * i for i in range(1, workers + 1)],
            [p.value for p in worker_procs]
        )

    def test_broadcast(self):

        env = simpy.Environment()
        bell_has_ringed = ConditionVar(env)
        ring_interval = 5
        workers = 5

        worker_procs = [env.process(waiter(env, bell_has_ringed))
                        for _ in range(workers)]

        env.process(
            signaler(env, lambda: bell_has_ringed.broadcast(),
                     ring_interval, lambda: env.now == 25)
        )

        env.run()

        self.assertListEqual(
            [5 for _ in range(workers)], [p.value for p in worker_procs]
        )


class TestBroadcastConditionVar(unittest.TestCase):

    def test_broadcast(self):

        env = simpy.Environment()
        bell_has_ringed = BroadcastConditionVar(env)
        ring_interval = 5
        workers = 5

        worker_procs = [env.process(waiter(env, bell_has_ringed))
                        for _ in range(workers)]

        env.process(
            signaler(env, lambda: bell_has_ringed.broadcast(),
                     ring_interval, lambda: env.now == 25)
        )

        env.run()

        self.assertListEqual(
            [ring_interval for _ in range(workers)],
            [p.value for p in worker_procs]
        )

