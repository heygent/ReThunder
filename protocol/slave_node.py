import copy
import simpy
import logging

from protocol.packet import Packet, PacketCodes, RequestPacket, ResponsePacket
from protocol.rethunder_node import ReThunderNode
from protocol.tracer import TracerCodes
from utils.run_process_decorator import run_process

HELLO_TIMEOUT = 500

logger = logging.getLogger(__name__)


class SlaveNode(ReThunderNode):

    def __init__(self, env: simpy.Environment, transmission_speed,
                 static_address, dynamic_address):

        super().__init__(env, transmission_speed,
                         static_address, dynamic_address)

        self.last_sent_noise_table = None
        self.__new_dynamic_address = None
        self.__response_waiting_address = None

        self.hello_timeout = HELLO_TIMEOUT
        self.run_until = lambda: False

    def __repr__(self):
        return '<SlaveNode static_address={}>'.format(self.static_address)

    def _on_message_received(self, payload):
        return None, 0

    def __set_new_dynamic_address(self, address):
        self.__new_dynamic_address = address

    def __update_dynamic_address(self):

        self.dynamic_address = (self.__new_dynamic_address or
                                self.dynamic_address)
        self.__new_dynamic_address = None

    def __i_am_next_hop(self, packet):

        i_am_next_hop = (packet.code_is_addressing_static and
                         self.static_address == packet.next_hop)

        i_am_next_hop |= (not packet.code_is_addressing_static and
                          self.dynamic_address == packet.next_hop)

        return i_am_next_hop

    @run_process
    def run_proc(self):

        while not self.run_until():

            received = yield self._receive_packet_proc()  # type: Packet

            if received.code == PacketCodes.hello:
                raise NotImplemented('SlaveNode received an hello message, '
                                     'which cannot be handled')

            response = None

            if isinstance(received, RequestPacket):
                response = self.__request_packet_received(received)

            if response is not None:
                yield self._send_to_network_proc(response,
                                                 response.number_of_frames())

    def __request_packet_received(self, packet: RequestPacket):

        if not self.__i_am_next_hop(packet):
            return None

        packet.source_static = self.static_address
        packet.source_logic = self.dynamic_address

        if packet.code_has_new_logic_addr:
            self.__set_new_dynamic_address(packet.new_logic_addr)

        if self.__response_waiting_address is not None:
            logger.error(
                '{} received {} while waiting for another RequestPacket. The '
                'packet will not be forwarded'.format(self, packet),
                extra={'request': copy.copy(packet)}
            )

        self.__response_waiting_address = packet.source_static

        if not packet.destination_reached():
            packet.next_hop = max(
                (dyn_address for dyn_address in self.routing_table.keys()
                 if dyn_address < packet.destination),
                self.dynamic_address
            )

            return packet

        if not packet.code_destination_is_endpoint:

            if packet.tracers_list[-1].offset == 0:

                code = packet.tracers_list.pop().code

                packet.code_is_addressing_static = bool(
                    code & TracerCodes.static_addressing.value
                )

                if code & TracerCodes.new_address.value:
                    packet.new_logic_addr = packet.path.pop()

            else:
                packet.tracers_list[-1].offset -= 1

            packet.destination = packet.path.pop()

            return packet

        return self.__make_response_packet(packet)

    def __make_response_packet(self, packet):

        logger.info('{} received a payload'.format(self),
                    extra={'payload': packet.payload})

        res_payload, res_payload_len = self._on_message_received(
            packet.payload
        )

        response = ResponsePacket()

        response.source_static = self.static_address
        response.source_logic = self.dynamic_address

        response.noise_tables.append(self.noise_table)

        response.payload = res_payload
        response.payload_length = res_payload_len

        return response

    def __response_packet_received(self, packet: ResponsePacket):

        if not self.__i_am_next_hop(packet):
            return None

        if self.__response_waiting_address is None:
            logger.warning('{} received a ResponseMessage for which there was '
                           'no answering address'.format(self))
            return None

        packet.source_static = self.static_address
        packet.source_logic = self.dynamic_address

        packet.next_hop = self.__response_waiting_address
        self.__response_waiting_address = None

        packet.noise_tables.append(self.noise_table)

        return packet
