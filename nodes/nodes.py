import simpy

from infrastructure.network_interface import NetworkInterface


class ReceiverNode:

    def __init__(self, env: simpy.Environment,
                 network_interface: NetworkInterface):

        self.env = env
        self.network_interface = network_interface
        self.received = []

    def receive_proc(self, until=lambda: False):

        env = self.env

        while not until():

            message = yield self.network_interface.receive_proc()
            self.received.append((env.now, message.value))


class SenderNode:

    def __init__(self, env, network_interface):

        self.env = env
        self.network_interface = network_interface
