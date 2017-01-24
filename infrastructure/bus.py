import logging
import weakref
from typing import Optional

import simpy

from infrastructure.message import TransmittedMessage, CollisionSentinel
from utils.condition_var import BroadcastConditionVar
from utils.simpy_process import simpy_process

logger = logging.getLogger(__name__)


class Bus:
    """
    Gli oggetti bus vengono utilizzati all'interno dell'infrastruttura per
    tenere in conto dei ritardi di propagazione tra i nodi. I bus vengono
    connessi ai nodi all'interno del grafo di rete, e i nodi connessi a
    questo condividono un canale di comunicazione avente il ritardo di
    propagazione stabilito.
    Alla ricezione del messaggio, il bus attende il tempo stabilito alla
    creazione prima di trasmettere il messaggio agli altri nodi connessi a
    esso, al termine del quale questi ricevono il messaggio.
    """

    def __init__(self, network, propagation_delay):
        """
        Inizializza un Bus.

        :param network: La rete in cui si vuole inserire il bus.
        :param propagation_delay: Il ritardo di propagazione, espresso in
        tempo di simulazione.
        """

        self.env = env = network.env
        self._netgraph = netgraph = weakref.proxy(network.netgraph)
        self._propagation_delay = propagation_delay
        self._current_send_proc = None
        self._message_in_transmission: Optional[TransmittedMessage] = None
        self._receive_current_transmission_cond = BroadcastConditionVar(env)

        netgraph.add_node(self)

    def __str__(self):
        return "<Bus>"

    @simpy_process
    def send_process(self, message):
        """
        Il processo che gestisce l'invio di un messaggio all'interno di un bus.

        L'invio funziona creando un processo che resta in esecuzione per la
        durata del ritardo di propagazione, al termine del quale il messaggio
        viene propagato ai nodi a cui il bus risulta vicino nel grafo di rete
        (se il grafo è diretto, per vicino si intende "nodo verso cui il bus
        ha un arco in uscita".)

        Se il bus riceve un messaggio durante l'esecuzione di un altro
        processo, il bus simula una collisione nel seguente modo:

        * Il processo precedente di invio viene terminato, senza pulire lo
        stato attuale di trasmissione del bus che contiene il messaggio
        precedente;

        * Un nuovo processo viene eseguito, il quale controlla lo stato del
        bus. Se un processo precedente è stato eseguito senza pulizia finale,
        vengono intraprese le operazioni per creare una collisione.

        :param message:
        :return:
        """

        env = self.env

        if self._current_send_proc is not None:
            self._current_send_proc.interrupt()

        self._current_send_proc = env.active_process

        if self._message_in_transmission is None:
            self._message_in_transmission = message
        else:
            logger.warning(f"{self}: A collision has happened between "
                           f"{message} and {self._message_in_transmission}")

            self._message_in_transmission = TransmittedMessage(
                CollisionSentinel,
                max(message.transmission_delay,
                    self._message_in_transmission.transmission_delay),
                None
            )

        try:
            yield env.timeout(self._propagation_delay)
        except simpy.Interrupt:
            return

        message = self._message_in_transmission
        self._message_in_transmission = None

        self._current_send_proc = None

        for node in self._netgraph.neighbors(self):
            if node is not message.sender:
                node.send_process(message)
