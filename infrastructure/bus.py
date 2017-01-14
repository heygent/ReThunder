import logging
import weakref
from typing import Optional

import simpy

from infrastructure.message import TransmittedMessage, CollisionSentinel
from utils.condition_var import BroadcastConditionVar
from utils.preemption_first_resource import PreemptionFirstResource
from utils.run_process_decorator import run_process

logger = logging.getLogger(__name__)


class Bus:

    def __init__(self, network, propagation_delay):

        self.env = env = network.env
        self._netgraph = netgraph = weakref.proxy(network.netgraph)
        self._propagation_delay = propagation_delay
        self._network_res = PreemptionFirstResource(env)
        self._message_in_transmission: Optional[TransmittedMessage] = None
        self._receive_current_transmission_cond = BroadcastConditionVar(env)

        netgraph.add_node(self)

    def __str__(self):
        return "<Bus>"

    @run_process
    def send_to_bus_proc(self, message):

        env = self.env

        if self._message_in_transmission is None:
            self._message_in_transmission = message
        else:
            logger.warning(f"{self}: A collision has happened between "
                           f"{message} and {self._message_in_transmission}")

            self._message_in_transmission = TransmittedMessage(
                CollisionSentinel,
                max(message.transmission_delay,
                    self._message_in_transmission.transmission_delay),
                None
            )

        with self._network_res.request(preempt=True) as req:
            try:
                yield req
                yield env.timeout(self._propagation_delay)

                message = self._message_in_transmission
                self._message_in_transmission = None

            except simpy.Interrupt:
                return

        for node in self._netgraph.neighbors(self):
            if node is not message.sender:
                node.send_to_node_proc(message)
