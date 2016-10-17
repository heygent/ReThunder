import collections
import simpy


class ConditionVar:

    def __init__(self, env: simpy.Environment):

        self.env = env  # type: simpy.Environment
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

    def __init__(self, env):
        self.env = env
        self.__signal_event = env.event()

    def wait(self):
        return self.__signal_event

    def broadcast(self, value=None):
        signal_event, self.__signal_event = (self.__signal_event,
                                             self.env.event())
        signal_event.succeed(value)
