from typing import NamedTuple

import simpy
from typing import List

from infrastructure.message import TransmittedMessage, CollisionSentinel
from infrastructure.network_interface import NetworkInterface
from utils.condition_var import BroadcastConditionVar
from utils.updatable_process import UpdatableProcess


class BusState(UpdatableProcess):

    occupy = UpdatableProcess.update

    def __init__(self, env: simpy.Environment, propagation_delay):

        super().__init__(env)
        self.env = env

        self.__propagation_delay = propagation_delay
        self.__current_message = None
        self.__current_transmission_ended = BroadcastConditionVar(env)
        self.__last_collision_time = None

    def _on_start(self, init_value):

        self.__current_message = init_value
        self.__last_collision_time = None
        self._stop_ev = self.env.timeout(self.__propagation_delay)

    def _on_update(self, update_value):

        new_message = update_value  # type: TransmittedMessage
        self.__last_collision_time = self.env.now

        collided_message = TransmittedMessage(
            CollisionSentinel,
            max(new_message.transmission_delay,
                self.__current_message.transmission_delay)
        )

        self.__current_message = collided_message

    def _on_stop(self, stop_value):

        message = self.__current_message  # type: TransmittedMessage

        if self.__last_collision_time is not None:
            collision_time_passed = (
                self.__last_collision_time - self._start_time
            )
            assert collision_time_passed >= 0
            msg_trans_delay = message.transmission_delay + collision_time_passed

            # noinspection PyProtectedMember
            message = message._replace(transmission_delay=msg_trans_delay)

        self.__current_transmission_ended.broadcast(message)

    def receive_current_transmission_ev(self) -> simpy.Event:
        return self.__current_transmission_ended.wait()


class Bus:

    def __init__(self, env, propagation_delay):

        self.env = env
        self.__bus_state = BusState(env, propagation_delay)
        self.__node_interface_list = []  # type: List[NetworkInterface]

    def register_node(self, node):
        self.__node_interface_list.append(node)

    def send_to_bus_proc(self, message):

        self.__bus_state.occupy(message)
        message = yield self.__bus_state.receive_current_transmission_ev()

        for node_interface in self.__node_interface_list:

            self.env.process(node_interface.send_to_node_proc(message))
