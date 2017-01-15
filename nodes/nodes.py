import collections
from typing import Any, List, Tuple, Iterable

from infrastructure.node import NetworkNode
from utils.run_process_decorator import run_process


class ReceiverNode(NetworkNode):

    def __init__(self, network):

        super().__init__(network)

        self.received: List[Tuple[int, Any]] = []
        self.run_until = lambda: False

    @run_process
    def run_proc(self):

        while not self.run_until():

            message = yield self._receive_process()
            self.received.append((self.env.now, message))


class SenderNode(NetworkNode):

    def __init__(self, network, send_queue: Iterable[Any]=()):

        super().__init__(network)
        self.__send_queue = collections.deque(iterable=send_queue)

    def send_next(self, message, message_len):
        self.__send_queue.append((message, message_len))

    @run_process
    def run_proc(self):

        send_queue = self.__send_queue

        while len(send_queue) > 0:
            msg_to_send = send_queue.popleft()
            yield self._transmit_process(*msg_to_send)
