"""
Contiene strutture e funzioni riguardanti i messaggi trasmessi.

La struttura che contiene le informazioni sui messaggi trasmessi è la
namedtuple TransmittedMessage. Questa contiene il contenuto, il ritardo di
trasmissione, e il nodo mittente del messaggio.

CollisionSentinel è il valore a cui `TransmittedMessage.value` viene settato in
caso di collisione del messaggio. I nodi possono testare se il messaggio
ricevuto è stato soggetto di una collisione con l'operatore `is`.
"""
from collections import namedtuple


class _CollisionSentinel:
    def __repr__(self):
        return '<CollidedMessage>'


CollisionSentinel = _CollisionSentinel()
del _CollisionSentinel


TransmittedMessage = namedtuple('TransmittedMessage',
                                'value, transmission_delay, sender')


def make_transmission_delay(transmission_speed: float, msg_length: int) -> int:
    """
    Calcola il ritardo di trasmissione di un messaggio a partire dalla
    velocità di trasmissione e dalla sua lunghezza.
    :param transmission_speed: La velocità di trasmissione.
    :param msg_length: La lunghezza del messaggio.
    :return: Il ritardo di trasmissione.
    """
    return max(int(msg_length / transmission_speed), 1)
