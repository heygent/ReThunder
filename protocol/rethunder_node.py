from infrastructure.message import CollisionSentinel
from infrastructure.network_interface import NetworkNode
from protocol.packet import Packet
from utils.run_process_decorator import run_process


class ReThunderNode(NetworkNode):

    def _update_noise_table(self, packet):
        raise NotImplemented

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

            if not isinstance(received_packet, Packet):
                raise TypeError("A ReThunderNode received something different "
                                "from a packet.")

            self._update_noise_table(received_packet)

            if not received_packet.is_readable():
                continue

            return received_packet

