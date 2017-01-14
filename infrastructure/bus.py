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

    @run_process
    def send_to_bus_proc(self, message):

        env = self.env

        with self._network_res.request(True) as req:
            yield req
            if self._message_in_transmission is None:
                self._message_in_transmission = message
            else:
                # todo collisione
                self._message_in_transmission = message
            try:
                yield env.timeout(self._propagation_delay)
            except simpy.Interrupt:
                return

        message = self._message_in_transmission

        for node in self._netgraph.neighbors(self):
            if node is not message.sender:
                node.send_to_node_proc(message)
