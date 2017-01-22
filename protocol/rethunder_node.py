import logging
from collections import defaultdict
from typing import Optional

import simpy

from infrastructure.message import CollisionSentinel
from infrastructure.node import NetworkNode
from protocol.packet import Packet, PacketWithSource, AckPacket
from utils import BroadcastConditionVar

logger = logging.getLogger(__name__)

RETRANSMISSIONS = 3
ACK_TIMEOUT = 200


class ReThunderNode(NetworkNode):

    def __init__(self, network, static_address: int,
                 logic_address: Optional[int]):

        super().__init__(network)
        self.static_address = static_address
        self.logic_address = logic_address
        self.noise_table = defaultdict(lambda: 0)
        self.routing_table = {}
        self._receive_packet_cond = BroadcastConditionVar(self.env)

        self._receive_current_transmission_cond.callbacks.append(
            self._check_packet_callback
        )

    def __repr__(self):
        return f'<ReThunderNode static_address={self.static_address}>'

    def _update_noise_table(self, packet: Packet):

        if isinstance(packet, PacketWithSource):
            self.noise_table[packet.source_static] = (
                int(packet.frame_error_average() * 1000)
            )

    def _update_routing_table(self, packet: Packet):

        if isinstance(packet, PacketWithSource):
            self.routing_table[packet.source_logic] = packet.source_static

    def _check_packet_callback(self, ev: simpy.Event):

        received = ev.value

        if received is CollisionSentinel:
            pass
        elif not isinstance(received, Packet):
            logger.error(f"{self} received something different from a packet")
        elif not received.is_readable():
            pass
        else:
            self._update_noise_table(received)
            self._update_routing_table(received)
            self._receive_packet_cond.broadcast(received)

    def _receive_packet_ev(self):
        return self._receive_packet_cond.wait()

    def _acknowledged_transmit(self, message, message_len):
        env = self.env

        for transmission in range(1, RETRANSMISSIONS + 1):

            self._transmit_process(message, message_len)
            to = env.timeout(ACK_TIMEOUT)

            while True:

                recv_ev = self._receive_packet_ev()
                cond_value = yield recv_ev | to

                if to in cond_value:

                    logger.info(f"No ack received for transmission "
                                f"{transmission} of token {message.token}")
                    return False

                elif recv_ev in cond_value:

                    received = recv_ev.value

                    if (isinstance(received, AckPacket) and
                            received.next_hop == self.static_address):
                        return True
                    else:
                        logger.info(f"{self} received something else while "
                                    f"waiting for ack of {message.token}")

    def _transmit_ack(self, message):

        if getattr(message, 'source_static', None) is None:
            return

        ack = AckPacket(of=message)
        self._transmit_process(ack, ack.number_of_frames())

