import logging
import weakref
from typing import Any, Optional

import simpy

from utils.condition_var import BroadcastConditionVar
from utils.preemption_first_resource import PreemptionFirstResource
from utils.run_process_decorator import run_process
from .message import (
    TransmittedMessage, CollisionSentinel, make_transmission_delay
)

logger = logging.getLogger(__name__)


class NetworkNode:

    timeout_sentinel = object()

    def __init__(self, network):

        self.env = env = network.env  # type: simpy.Environment

        self._netgraph = netgraph = weakref.proxy(network.netgraph)
        self._network_res = PreemptionFirstResource(env)
        self._receive_current_transmission_cond = BroadcastConditionVar(env)
        self._message_in_transmission: Optional[TransmittedMessage] = None
        self._transmission_speed = network.transmission_speed

        netgraph.add_node(self)

    @run_process
    def _send_to_network_proc(self, message_val: Any, message_len: int):
        env = self.env

        with self._network_res.request(preempt=False) as req:
            yield req
            # todo: Possibile punto di collisione
            self._message_in_transmission = message_val

            transmission_delay = make_transmission_delay(
                self._transmission_speed, message_len
            )

            message = TransmittedMessage(message_val, transmission_delay, self)

            for bus in self._netgraph.neighbors(self):
                bus.send_to_bus_proc(message)

            try:
                yield env.timeout(transmission_delay)
            except simpy.Interrupt:
                return

            self._message_in_transmission = None

    @run_process
    def send_to_node_proc(self, message: TransmittedMessage):
        env = self.env

        if self._message_in_transmission is None:
            self._message_in_transmission = message
            transmission_delay = message.transmission_delay
        else:
            # todo correggi ritardo di trasmissione
            transmission_delay = max(
                message.transmission_delay,
                self._message_in_transmission.transmission_delay
            )
            self._message_in_transmission = TransmittedMessage(
                CollisionSentinel,
                transmission_delay,
                None
            )
        with self._network_res.request(preempt=True) as req:
            try:
                yield req
                yield env.timeout(transmission_delay)
            except simpy.Interrupt:
                return

        message = self._message_in_transmission
        self._message_in_transmission = None

        self._receive_current_transmission_cond.broadcast(message)

    @run_process
    def _receive_proc(self, timeout=None):

        env = self.env

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

        received = self._receive_current_transmission_cond.wait()

        yield received or to

        if received.processed:
            transmitted_msg = received.value
            return transmitted_msg.value
        if to.processed:
            return self.timeout_sentinel
