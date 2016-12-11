import logging
from collections import defaultdict

from infrastructure.message import CollisionSentinel
from infrastructure.network_node import NetworkNode
from protocol.packet import Packet, PacketWithSource
from utils.run_process_decorator import run_process

logger = logging.getLogger(__name__)


class ReThunderNode(NetworkNode):

    def __init__(self, env, transmission_speed, static_address,
                 logic_address):

        super().__init__(env, transmission_speed)
        self.static_address = static_address
        self.logic_address = logic_address
        self.noise_table = defaultdict(lambda: 0)
        self.routing_table = {}

    def __repr__(self):
        return '<ReThunderNode static_address={}>'.format(
            self.static_address, self.logic_address
        )

    def _update_noise_table(self, packet: Packet):

        if isinstance(packet, PacketWithSource):
            self.noise_table[packet.source_static] = (
                int(packet.frame_error_average() * 1000)
            )

    def _update_routing_table(self, packet: Packet):

        if isinstance(packet, PacketWithSource):
            self.routing_table[packet.source_static] = packet.source_logic

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
