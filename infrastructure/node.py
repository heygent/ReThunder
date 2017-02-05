import logging
import weakref
from typing import Any, Optional

import simpy

from utils.condition_var import BroadcastConditionVar
from utils.simpy_process import simpy_process
from .message import (
    TransmittedMessage, CollisionSentinel, make_transmission_delay
)

logger = logging.getLogger(__name__)


class NetworkNode:
    """
    Classe di base dei nodi nella rete del simulatore.

    I nodi nel simulatore devono essere sottoclassi di NetworkNode. Questa
    classe fornisce l'interfaccia per la trasmissione e la ricezione di
    messaggi e gestisce le collisioni.

    Le collisioni vengono gestite tenendo un processo di invio attivo quando la
    rete è occupata, per ricezione o trasmissione. La trasmissione quando la
    rete è occupata viene rinviata.
    Nello stato interno del nodo, viene tenuto un riferimento al messaggio
    correntemente in trasmissione. Quando più di un processo d'invio è
    presente e in stato d'invio, il primo di questi viene interrotto,
    lasciando lo stato interno "sporco", ovvero contenente il precendente
    messaggio in trasmissione.
    Il nuovo processo d'invio usa il suo messaggio assieme a questo per
    creare un messaggio di collisione.
    Il processo, quindi, attende una quantità di tempo pari al ritardo di
    trasmissione del messaggio, durante la quale possono verificarsi nuove
    collisioni reiterando quanto descritto.

    """

    def __init__(self, network):

        self.env = env = network.env  # type: simpy.Environment

        self._netgraph = netgraph = weakref.proxy(network.netgraph)
        self._transmission_speed = network.transmission_speed
        self._current_occupy_proc = None
        self._receive_current_transmission_cond = BroadcastConditionVar(env)
        self._message_in_transmission: Optional[TransmittedMessage] = None
        self._last_transmission_start = None

        netgraph.add_node(self)

    @simpy_process
    def _transmit_process(self, message_val: Any, message_len: int):
        """
        Invia un messaggio dal nodo alla rete.

        :param message_val: Il contenuto del messaggio.
        :param message_len: La lunghezza relativa del messaggio.
        :return: Il processo che esegue l'operazione descritta.
        """

        transmission_delay = make_transmission_delay(
            self._transmission_speed, message_len
        )

        message = TransmittedMessage(message_val, transmission_delay, self)

        yield from self.__occupy(message, in_transmission=True)

    @simpy_process
    def send_process(self, message: TransmittedMessage):
        """
        Invia un messaggio al nodo.
        :param message: Il TransmittedMessage da mandare al nodo.
        :return: Il processo che esegue l'operazione descritta.
        """

        yield from self.__occupy(message, in_transmission=False)

    def _receive_ev(self):
        """
        Restituisce un evento che scatta alla prossima ricezione del
        messaggio da parte del nodo.
        Il valore dell'evento sarà il messaggio ricevuto.
        :return: Un evento per ricevere messaggi.
        """
        return self._receive_current_transmission_cond.wait()

    def __occupy(self, message: TransmittedMessage, in_transmission):
        """
        Generatore che esegue le operazioni di trasmissione e ricezione.

        Viene
        :param message:
        :param in_transmission:
        :return:
        """
        env = self.env
        this_proc = env.active_process

        if in_transmission:
            while self._current_occupy_proc is not None:
                yield self._current_occupy_proc
        else:
            if self._current_occupy_proc is not None:
                self._current_occupy_proc.interrupt()

        self._current_occupy_proc = this_proc

        last_transmission_start = self._last_transmission_start
        self._last_transmission_start = env.now

        if self._message_in_transmission is None:
            self._message_in_transmission = message
            to_wait = message.transmission_delay
        else:
            logger.warning(f"{self}: A collision has happened between "
                           f"{message} and {self._message_in_transmission}")

            last_occupation_time = env.now - last_transmission_start

            remaining_occupation_time = (
                self._message_in_transmission.transmission_delay -
                last_occupation_time
            )

            to_wait = max(message.transmission_delay,
                          remaining_occupation_time)

            self._message_in_transmission = TransmittedMessage(
                CollisionSentinel,
                last_occupation_time + to_wait,
                None
            )

        if in_transmission:
            for n in self._netgraph.neighbors(self):
                n.send_process(message)

        try:
            yield env.timeout(to_wait)
        except simpy.Interrupt:
            return

        message = self._message_in_transmission
        self._message_in_transmission = None

        self._current_occupy_proc = None

        if not in_transmission:
            self._receive_current_transmission_cond.broadcast(message.value)
