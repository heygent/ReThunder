import collections

import simpy


class ConditionVar:

    def __init__(self, env: simpy.Environment):

        self.env: simpy.Environment = env
        self.__signal_events = collections.deque()

    def wait(self) -> simpy.Event:
        event = self.env.event()
        self.__signal_events.appendleft(event)
        return event

    def priority_wait(self):
        event = self.env.event()
        self.__signal_events.append(event)
        return event

    def signal(self, value=None):

        try:
            self.__signal_events.pop().succeed(value)
        except IndexError:
            pass

    def broadcast(self, value=None):
        for event in self.__signal_events:
            event.succeed(value)
        self.__signal_events.clear()


class BroadcastConditionVar:

    def __init__(self, env, callbacks=None):
        self.env = env
        self.callbacks = callbacks or []
        self._signal_ev = self.env.event()

    def wait(self):
        return self._signal_ev

    def broadcast(self, value=None):
        signal_ev, self._signal_ev = self._signal_ev, self.env.event()
        signal_ev.callbacks.extend(self.callbacks)
        signal_ev.succeed(value)
