import simpy

from infrastructure.message import TransmittedMessage, CollisionSentinel
from utils.condition_var import BroadcastConditionVar
from utils.run_process_decorator import run_process
from utils.updatable_process import UpdatableProcess


class BusState(UpdatableProcess):
    """
    Rappresenta lo stato di un Bus.

    Un Bus puo' essere libero o occupato. Quando un bus libero riceve un
    messaggio, va in stato occupato. Se un Bus riceve un messaggio mentre si
    trova in stato di occupato, il messaggio all'interno del bus riceve una
    trasformazione corrispondente alla collusione tra i due messaggi,
    ovvero il messaggio viene sostituito con un riferimento all'oggetto
    sentinella CollidedMessage.
    """

    occupy = UpdatableProcess.update

    def __init__(self, env: simpy.Environment, propagation_delay):
        """
        Inizializzatore per BusState. I BusState dovrebbero essere
        inizializzati unicamente dagli oggetti Bus.

        :param env: L'ambiente della simulazione.
        :param propagation_delay: Il ritardo di propagazione.
        """

        super().__init__(env)

        self.on_collision = None

        self.__propagation_delay = propagation_delay
        self.__current_message = None
        self.__current_transmission_ended = BroadcastConditionVar(env)
        self.__last_collision_time = None

    @property
    def current_message(self):
        return self.__current_message

    @property
    def last_collision_time(self):
        return self.__last_collision_time

    @property
    def propagation_delay(self):
        return self.__propagation_delay

    def _on_start(self, init_value):

        self.__current_message = init_value
        self.__last_collision_time = None
        self._stop_ev = self.env.timeout(self.__propagation_delay)

    def _on_update(self, update_value):

        new_message = update_value  # type: TransmittedMessage
        self.__last_collision_time = self.env.now

        try:
            self.on_collision(self, new_message)
        except TypeError:
            pass

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
        self.__node_list = []

    def register_node(self, node, mutual=True):
        self.__node_list.append(node)
        if mutual:
            node.register_bus(self, False)

    @property
    def on_collision(self):
        return self.__bus_state.on_collision

    @on_collision.setter
    def on_collision(self, other):
        self.__bus_state.on_collision = other

    @run_process
    def send_to_bus_proc(self, message):

        self.__bus_state.occupy(message)
        message = yield self.__bus_state.receive_current_transmission_ev()

        for node in self.__node_list:

            node.send_to_node_proc(message)
