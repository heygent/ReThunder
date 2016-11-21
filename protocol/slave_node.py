from collections import defaultdict

import simpy

from protocol.packet import Packet, PacketCodes, RequestPacket, ResponsePacket
from protocol.rethunder_node import ReThunderNode
from utils.run_process_decorator import run_process

HELLO_TIMEOUT = 500


class SlaveNode(ReThunderNode):

    def __init__(self, env: simpy.Environment, transmission_speed):

        super().__init__(env, transmission_speed)

        self.static_address = None
        self.dynamic_address = None
        self.physical_address = None
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










