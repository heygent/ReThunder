import logging
from collections import defaultdict

from infrastructure.message import CollisionSentinel
from infrastructure.network_interface import NetworkNode
from protocol.packet import Packet
from utils.run_process_decorator import run_process

logger = logging.getLogger(__name__)


class ReThunderNode(NetworkNode):

    def __init__(self, env, timeout):
        super().__init__(env, timeout)
        self.noise_table = defaultdict(lambda: 0)
        self.routing_table = {}

    def __repr__(self):
        return '<ReThunderNode static_address={}>'.format(
            self.static_address, self.dynamic_address
        )

    def _update_noise_table(self, packet):
        try:
            self.noise_table[packet.source_static] = (
                int(packet.frame_error_average() * 1000)
            )
        except AttributeError:
            pass

    def _update_routing_table(self, packet):
        try:
            self.routing_table[packet.source_static] = packet.source_dynamic
        except AttributeError:
            pass

    @run_process
    def _receive_packet_proc(self, timeout=None):

        if isinstance(timeout, int):
            timeout = self.env.timeout(timeout)

        while True:

            received_packet = yield self._receive_proc(timeout)

            if received_packet is CollisionSentinel:
                continue

            if received_packet is self.timeout_sentinel:
                return self.timeout_sentinel

            self._update_noise_table(received_packet)
            self._update_routing_table(received_packet)

            if not isinstance(received_packet, Packet):
                logger.error(
                    "{} received something different from a "
                    "packet".format(self)
                )
                continue

            if not received_packet.is_readable():
                continue

            return received_packet

