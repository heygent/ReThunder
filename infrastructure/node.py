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
        self._transmission_speed = network.transmission_speed
        self._network_res = PreemptionFirstResource(env)
        self._receive_current_transmission_cond = BroadcastConditionVar(env)
        self._message_in_transmission: Optional[TransmittedMessage] = None
        self._last_transmission_start = None

        netgraph.add_node(self)

    @run_process
    def _transmit_process(self, message_val: Any, message_len: int):

        transmission_delay = make_transmission_delay(
            self._transmission_speed, message_len
        )

        message = TransmittedMessage(message_val, transmission_delay, self)

        yield from self._occupy(message, in_transmission=True)

    @run_process
    def send_process(self, message: TransmittedMessage):

        yield from self._occupy(message, in_transmission=False)

    @run_process
    def _receive_process(self, timeout=None):

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
            transmitted_msg: TransmittedMessage = received.value
            return transmitted_msg.value
        if to.processed:
            return self.timeout_sentinel

    def _occupy(self, message: TransmittedMessage, in_transmission):
        env = self.env

        last_transmission_start = self._last_transmission_start
        self._last_transmission_start = env.now

        with self._network_res.request(preempt=not in_transmission) as req:
            yield req

            if self._message_in_transmission is None:
                self._message_in_transmission = message
                to_wait = message.transmission_delay
            else:
                logger.warning(f"{self}: A collision has happened between "
                               f"{message} and {self._message_in_transmission}")

                if in_transmission:
                    logger.error(
                        f"{self}: Collision has happened as a consequence of a "
                        f"transmission by the node. This should not happen."
                    )

                last_occupation_time = env.now - last_transmission_start

                remaining_occupation_time = (
                    self._message_in_transmission.transmission_delay -
                    last_occupation_time
                )

                to_wait = max(message.transmission_delay,
                              remaining_occupation_time)

                self._message_in_transmission = TransmittedMessage(
                    CollisionSentinel,
                    last_occupation_time + to_wait,
                    None
                )

            if in_transmission:
                for bus in self._netgraph.neighbors(self):
                    bus.send_process(message)

            try:
                yield env.timeout(to_wait)
            except simpy.Interrupt:
                return

            message = self._message_in_transmission
            self._message_in_transmission = None

            if not in_transmission:
                self._receive_current_transmission_cond.broadcast(message)
