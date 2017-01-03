import logging
from collections import defaultdict
from typing import Optional

from infrastructure.message import CollisionSentinel
from infrastructure.node import NetworkNode
from protocol.packet import Packet, PacketWithSource, AckPacket
from utils.run_process_decorator import run_process

logger = logging.getLogger(__name__)

RETRANSMISSIONS = 3
ACK_TIMEOUT = 15


class ReThunderNode(NetworkNode):

    def __init__(self, network, static_address: int,
                 logic_address: Optional[int]):

        super().__init__(network)
        self.static_address = static_address
        self.logic_address = logic_address
        self.noise_table = defaultdict(lambda: 0)
        self.routing_table = {}

    def __repr__(self):
        return '<ReThunderNode static_address={}>'.format(self.static_address)

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

            logger.debug(f'{self} received a packet.')

            return received_packet

    def _send_and_acknowledge(self, to_send: Packet):

        token = to_send.token
        transmissions = 0
        transmit = True

        while transmissions < RETRANSMISSIONS:

            if transmit:

                transmissions += 1
                transmit = False
                yield self._send_to_network_proc(
                    to_send, to_send.number_of_frames()
                )

            received = yield self._receive_packet_proc(ACK_TIMEOUT)

            if received is self.timeout_sentinel:
                transmit = True

            elif isinstance(received, AckPacket):
                if (received.next_hop == self.static_address and
                        received.token == token):
                    return True
            else:
                logger.warning("{} was waiting for ack, received something "
                               "else. Ignoring".format(self))

        return False

    def _send_ack(self, packet):

        if getattr(packet, 'source_static', None) is None:
            return

        ack = AckPacket(of=packet)

        yield self._send_to_network_proc(ack, ack.number_of_frames())
