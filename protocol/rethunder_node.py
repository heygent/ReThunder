import logging
from typing import Optional

import simpy

from infrastructure.message import CollisionSentinel
from infrastructure.node import NetworkNode
from protocol.packet import Packet, PacketWithSource, AckPacket
from utils import BroadcastConditionVar

logger = logging.getLogger(__name__)


class ReThunderNode(NetworkNode):

    def __init__(self, network, static_address: int,
                 logic_address: Optional[int]):

        super().__init__(network)
        self.static_address = static_address
        self.logic_address = logic_address
        self.noise_table = {}
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

