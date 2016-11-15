from infrastructure.message import CollisionSentinel
from infrastructure.network_interface import NetworkNode
from protocol.packet import Packet
from utils.run_process_decorator import run_process


class ReThunderNode(NetworkNode):

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
                raise TypeError("A SlaveNode received something different "
                                "from a packet.")

            frame_errors = [max(error_count, 2) for _, error_count in
                            received_packet.damaged_frames()]

            error_average = (
                sum(frame_errors) / received_packet.number_of_frames
            )

            try:
                self.noise_table[received_packet.source_static] = error_average
            except AttributeError:
                pass

            if any(error_count >= 2 for error_count in frame_errors):
                continue

            return received_packet

