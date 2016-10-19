from typing import Generator, Any
from typing import List

import simpy

from utils.condition_var import ConditionVar, BroadcastConditionVar
from utils.process_decorator import run_process
from utils.updatable_process import UpdatableProcess

import infrastructure.bus
from .message import TransmittedMessage, CollisionSentinel, \
    make_transmission_delay


class NetworkState(UpdatableProcess):

    occupy = UpdatableProcess.update

    def __init__(self, env: simpy.Environment):

        super().__init__(env)

        self.__network_is_free = ConditionVar(self.env)
        self.__current_transmission_ended = BroadcastConditionVar(self.env)
        self.__current_message = None

    def wait_free_network_ev(self) -> simpy.Event:
        return self.__network_is_free.wait()

    def receive_current_transmission_ev(self) -> simpy.Event:
        return self.__current_transmission_ended.wait()

    @property
    def network_is_busy(self):
        return self._running

    def _on_start(self, init_value):

        self.__current_message = init_value

        self._stop_ev = self.env.timeout(
            self.__current_message.transmission_delay
        )

    def _on_update(self, update_value):

        env = self.env

        occupation_time_passed = (env.now - self._start_time)

        occupation_time_left = (self.__current_message.transmission_delay -
                                occupation_time_passed)

        assert occupation_time_left > 0

        new_message = update_value  # type: TransmittedMessage

        new_occupation_time_left = max(
            new_message.transmission_delay, occupation_time_left
        )

        self._stop_ev = env.timeout(new_occupation_time_left)

        self.__current_message = TransmittedMessage(
            CollisionSentinel,
            occupation_time_passed + new_occupation_time_left
        )

    def _on_stop(self, _):

        message, self.__current_message = self.__current_message, None
        self.__network_is_free.signal()
        self.__current_transmission_ended.broadcast(message)


class NetworkNode:

    timeout_sentinel = object()

    def __init__(self, env, transmission_speed,
                 collision_callback=lambda x, y: CollisionSentinel):

        self.env = env  # type: simpy.Environment

        self.collision_callback = collision_callback

        self.__bus_list = []
        self.__network_state = NetworkState(self.env)
        self.__transmission_speed = transmission_speed

    @run_process
    def _send_to_network_proc(self, message_val: Any, message_len: int):

        yield self.__network_state.wait_free_network_ev()

        transmission_delay = make_transmission_delay(
            self.__transmission_speed, message_len
        )

        message = TransmittedMessage(message_val, transmission_delay)

        for bus in self.__bus_list:
            bus.send(message)

        self.__network_state.occupy(message)

    def register_bus(self, bus, mutual=False):
        self.__bus_list.append(bus)
        if mutual:
            bus.register_node(self, False)

    @run_process
    def send_to_node_proc(self, message: TransmittedMessage):
        self.__network_state.occupy(message)

    @run_process
    def _receive_proc(self, timeout=None):

        env = self.env

        if timeout is None:
            to = env.event()
        else:
            to = env.timeout(timeout, value=self.timeout_sentinel)

        return (yield self.__network_state.receive_current_transmission_ev()
                or to)

