import simpy

from protocol.packet import Packet, PacketCodes, RequestPacket, ResponsePacket
from protocol.rethunder_node import ReThunderNode
from protocol.tracer import TracerCodes
from utils.run_process_decorator import run_process

HELLO_TIMEOUT = 500


class SlaveNode(ReThunderNode):

    def __init__(self, env: simpy.Environment, transmission_speed,
                 static_address, dynamic_address):

        super().__init__(env, transmission_speed,
                         static_address, dynamic_address)

        self.last_sent_noise_table = None

        self.hello_timeout = HELLO_TIMEOUT
        self.run_until = lambda: False

    def _payload_received(self, payload):
        return None, 0

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

        i_am_next_hop = (packet.code_is_addressing_static and
                         self.static_address == packet.next_hop)

        i_am_next_hop |= (not packet.code_is_addressing_static and
                          self.dynamic_address == packet.next_hop)

        if not i_am_next_hop:
            return None

        packet.source_static = self.static_address
        packet.source_logic = self.dynamic_address

        if packet.next_hop != packet.destination:

            packet.destination = max(
                (dyn_address for dyn_address in self.routing_table.keys()
                 if dyn_address < packet.destination),
                self.dynamic_address
            )

            return packet

        if packet.code_destination_is_endpoint:

            next_address = packet.path.pop()

            if packet.tracers_list[-1].offset == 0:

                code = packet.tracers_list.pop().code

                packet.code_is_addressing_static = bool(
                    code & TracerCodes.static_addressing.value
                )

                if code & TracerCodes.new_address.value:
                    self.dynamic_address = next_address
                    next_address = packet.path.pop()

            else:
                packet.tracers_list[-1].offset -= 1

            packet.destination = next_address

            return packet

        # I'm the endpoint

        res_payload, res_payload_len = self._payload_received(
            packet.payload
        )

        response = ResponsePacket()

        response.source_static = self.static_address
        response.source_logic = self.dynamic_address

        response.noise_tables.append(self.noise_table)

        response.payload = res_payload
        response.payload_length = res_payload_len

        return response


