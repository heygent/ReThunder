import logging
from copy import copy
from typing import Optional

from protocol.packet import (
    Packet, RequestPacket, ResponsePacket, PacketWithSource, AddressType
)
from protocol.rethunder_node import ReThunderNode
from utils.func import singledispatchmethod
from utils.run_process_decorator import run_process

logger = logging.getLogger(__name__)


class SlaveNode(ReThunderNode):

    def __init__(self, network, static_address: int,
                 logic_address: Optional[int]=None, on_message_received=None):

        super().__init__(network, static_address, logic_address)

        self.last_sent_routing_table = {}
        self._previous_node_static_addr = None
        self._ack_pending_token = None

        self.run_until = lambda: False
        self.on_message_received = on_message_received or (lambda x, y, z: None)

    def __repr__(self):
        return '<SlaveNode static_address={}>'.format(self.static_address)

    @run_process
    def run_proc(self):

        while not self.run_until():

            received = yield self._receive_packet_proc()  # type: Packet
            response = self._handle_received(received)  # type: Packet

            if response is not None:
                self._send_to_network_proc(
                    response, response.number_of_frames()
                )

    def _is_destination_of(self, packet):
        if packet.code_is_addressing_static:
            return self.static_address == packet.destination
        else:
            return self.logic_address == packet.destination

    @singledispatchmethod
    def _handle_received(self, _):
        logger.error(f'{self} received something unsupported.')

    @_handle_received.register(Packet)
    def _(self, packet):
        logger.warning(f'{self} received {packet}, which cannot be handled.')

    @_handle_received.register(RequestPacket)
    def _request_packet_received(self, packet: RequestPacket):

        if packet.next_hop != self.static_address:
            return None

        self._previous_node_static_addr = packet.source_static

        new_logic_addr = packet.new_logic_addresses.get(self.static_address)

        if new_logic_addr is not None:
            self.logic_address = new_logic_addr

        packet.source_static = self.static_address
        packet.source_logic = self.logic_address

        if not self._is_destination_of(packet):

            routing_table = self.last_sent_routing_table

            next_logic_hop = max(
                (addr for addr in routing_table.keys()
                 if addr < packet.destination),
                self.logic_address
            )

            packet.next_hop = routing_table[next_logic_hop]

            return packet

        elif not packet.code_destination_is_endpoint:

            dest_type, dest = packet.path.pop()
            packet.destination = dest
            packet.code_is_addressing_static = dest_type is AddressType.static

            return packet

        else:
            return self._make_response_packet(packet)

    @_handle_received.register(ResponsePacket)
    def _response_packet_received(self, packet):

        if packet.next_hop != self.static_address:
            return None

        if self._previous_node_static_addr is None:
            logger.warning(
                f'{self} received a ResponseMessage for which there was '
                'no answering address'
            )
            return None

        packet.source_static = self.static_address
        packet.source_logic = self.logic_address

        packet.next_hop = self._previous_node_static_addr

        packet.noise_tables.append(self.noise_table)

        return packet

    def _make_response_packet(self, packet):

        logger.info(f'{self} received a payload')

        response = ResponsePacket()

        response.source_static = self.static_address
        response.source_logic = self.logic_address
        response.next_hop = packet.source_static
        response.token = packet.token

        response.noise_tables.append(copy(self.noise_table))
        self.last_sent_routing_table = copy(self.routing_table)

        response.payload, response.payload_length = self.on_message_received(
            self, packet.payload, packet.payload_length
        )

        return response
