import itertools
import collections
from typing import Any, List, Tuple

import simpy

from infrastructure.network_interface import NetworkInterface
from utils.process_decorator import run_process


class ReceiverNode:

    def __init__(self, network_interface: NetworkInterface):

        self.env = network_interface.env            # type: simpy.Environment
        self.network_interface = network_interface  # type: NetworkInterface

        self.received = []  # type: List[Tuple[int, Any]]
        self.run_until = lambda: False

    @run_process
    def run_proc(self):

        while not self.run_until():

            message = yield self.network_interface.receive_proc()
            self.received.append((self.env.now, message))


class SenderNode:

    def __init__(self, network_interface):

        self.env = self.network_interface.env       # type: simpy.Environment
        self.network_interface = network_interface  # type: NetworkInterface

        self.__send_queue = collections.deque()
        self.__insertion_index = itertools.count()

    def send_next(self, message, message_len):
        self.__send_queue.append((message, message_len))

    @run_process
    def run_proc(self):

        send_queue = self.__send_queue

        while len(send_queue) > 0:
            msg_to_send = send_queue.pop()
            yield self.network_interface.send_to_network_proc(*msg_to_send)
