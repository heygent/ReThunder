from collections import defaultdict

import simpy

from protocol.packet import PacketCodes, HelloRequestPacket, PacketWithSource
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
    def hello_proc(self):

        hello_packet = HelloRequestPacket()
        hello_packet.physical_address = self.physical_address

        while not self.run_until():

            # todo usa unita' di misura coerente per la lunghezza dei messaggi
            yield self._send_to_network_proc(
                hello_packet, hello_packet.number_of_frames()
            )

            received = yield self._receive_packet_proc(self.hello_timeout)

            if received.code == PacketCodes.hello_response:
                raise NotImplemented

    @run_process
    def run_proc(self):

        yield self.hello_proc()

        while not self.run_until():

            received = yield self._receive_packet_proc()



