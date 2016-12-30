import logging
from copy import copy, deepcopy
from typing import Optional

from protocol.packet import (
    Packet, RequestPacket, ResponsePacket, PacketWithSource
)
from protocol.rethunder_node import ReThunderNode
from protocol.tracer import Tracer
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

            if isinstance(received, PacketWithSource):
                yield from self._send_ack(received)

            response = self._handle_received(received)  # type: Packet

            if response is not None:
                yield from self._send_and_acknowledge(response)

    def _is_destination_of(self, packet):
        if packet.code_is_addressing_static:
            return self.static_address == packet.destination
        else:
            return self.logic_address == packet.destination

    @singledispatchmethod
    def _handle_received(self, received):

        logger.error(
            '{} received something unsupported.'.format(self),
            extra={'received': received}
        )

    @_handle_received.register(Packet)
    def _(self, packet):

        logger.warning(
            '{} received {}, which cannot be handled.'
            .format(self, packet), extra={'packet': deepcopy(packet)}
        )

    @_handle_received.register(RequestPacket)
    def _request_packet_received(self, packet):

        if packet.next_hop != self.static_address:
            return None

        packet.source_static = self.static_address
        packet.source_logic = self.logic_address

        if packet.new_logic_addr is not None:
            self.logic_address = packet.new_logic_addr

        self._previous_node_static_addr = packet.source_static

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

            if packet.tracers_list[-1].offset == 0:
                tracer = packet.tracers_list.pop()
            else:
                packet.tracers_list[-1].offset -= 1
                tracer = Tracer()

            packet.code_is_addressing_static = tracer.static_addressing

            if tracer.new_address:
                packet.new_logic_addr = packet.path.pop()

            packet.destination = packet.path.pop()

            return packet

        else:
            return self._make_response_packet(packet)

    @_handle_received.register(ResponsePacket)
    def _response_packet_received(self, packet):

        if packet.next_hop != self.static_address:
            return None

        if self._previous_node_static_addr is None:
            logger.warning('{} received a ResponseMessage for which there was '
                           'no answering address'.format(self))
            return None

        packet.source_static = self.static_address
        packet.source_logic = self.logic_address

        packet.next_hop = self._previous_node_static_addr

        packet.noise_tables.append(self.noise_table)

        return packet

    def _make_response_packet(self, packet):

        logger.info('{} received a payload'.format(self),
                    extra={'payload': packet.payload})

        response = ResponsePacket()

        response.source_static = self.static_address
        response.source_logic = self.logic_address
        response.next_hop = packet.source_static
        response.token = packet.token

        response.noise_tables.append(copy(self.noise_table))
        self.last_sent_routing_table = self.routing_table

        response.payload, response.payload_length = self.on_message_received(
            self, packet.payload, packet.payload_length
        )

        return response
