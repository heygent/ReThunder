import logging
import weakref
from typing import Any

import simpy

from utils.condition_var import ConditionVar, BroadcastConditionVar
from utils.run_process_decorator import run_process
from utils.updatable_process import UpdatableProcess
from .message import (
    TransmittedMessage, CollisionSentinel, make_transmission_delay
)

logger = logging.getLogger(__name__)


class NetworkState(UpdatableProcess):

    occupy = UpdatableProcess.update

    def __init__(self, env: simpy.Environment, owner=None):

        super().__init__(env)

        self.__network_is_free = ConditionVar(self.env)
        self.__current_transmission_ended = BroadcastConditionVar(self.env)
        self._current_message = None

        if owner is None:
            self._owner = lambda: None
        else:
            self._owner = weakref.ref(owner)

    def wait_free_network_ev(self) -> simpy.Event:
        return self.__network_is_free.wait()

    def receive_current_transmission_ev(self) -> simpy.Event:
        return self.__current_transmission_ended.wait()

    @property
    def network_is_busy(self):
        return self._running

    def _on_start(self, init_value):

        self._current_message = init_value

        self._stop_ev = self.env.timeout(
            self._current_message.transmission_delay
        )

    def _on_update(self, update_value):

        env = self.env

        occupation_time_passed = (env.now - self._start_time)

        occupation_time_left = (self._current_message.transmission_delay -
                                occupation_time_passed)

        logger.info(
            f"{self._owner()!r}: A collision has happened between "
            f"{self._current_message} and {update_value}"
        )
        assert occupation_time_left > 0

        new_message = update_value  # type: TransmittedMessage

        new_occupation_time_left = max(
            new_message.transmission_delay, occupation_time_left
        )

        self._stop_ev = env.timeout(new_occupation_time_left)

        self._current_message = TransmittedMessage(
            CollisionSentinel,
            occupation_time_passed + new_occupation_time_left,
            None
        )

    def _on_stop(self, _):

        message, self._current_message = self._current_message, None
        self.__network_is_free.signal()
        self.__current_transmission_ended.broadcast(message)


class NetworkNode:

    timeout_sentinel = object()

    def __init__(self, network):

        self.env = network.env  # type: simpy.Environment

        self._netgraph = netgraph = weakref.proxy(network.netgraph)
        self._network_state = NetworkState(self.env, self)
        self._transmission_speed = network.transmission_speed

        netgraph.add_node(self)

    @run_process
    def _send_to_network_proc(self, message_val: Any, message_len: int):

        if self._network_state.network_is_busy:
            yield self._network_state.wait_free_network_ev()

        transmission_delay = make_transmission_delay(
            self._transmission_speed, message_len
        )

        message = TransmittedMessage(message_val, transmission_delay, self)

        for bus in self._netgraph.neighbors(self):
            bus.send_to_bus_proc(message)

        self._network_state.occupy(message)

    @run_process
    def send_to_node_proc(self, message: TransmittedMessage):
        # Make it a generator for eventual future changes that may require
        # yielding events
        if False:
            yield

        self._network_state.occupy(message)

    @run_process
    def _receive_proc(self, timeout=None):

        env = self.env

        received = self._network_state.receive_current_transmission_ev()

        if timeout is None:
            to = env.event()
        elif isinstance(timeout, simpy.Event):
            to = timeout
        elif isinstance(timeout, int):
            to = env.timeout(timeout)
        else:
            raise TypeError(
                'timeout can be None, an integer or an event.'
            )

        while True:
            yield received or to
            yield env.timeout(0)

            assert any(e.processed for e in (received, to)), "Spurious wake"

            if received.processed:
                transmitted_msg = received.value
                if transmitted_msg.sender is not self:
                    return transmitted_msg.value
                else:
                    received = \
                        self._network_state.receive_current_transmission_ev()
            if to.processed:
                return self.timeout_sentinel

