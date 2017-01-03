from collections import namedtuple


class _CollisionSentinel:
    def __repr__(self):
        return '<CollidedMessage>'


CollisionSentinel = _CollisionSentinel()
del _CollisionSentinel


_TransmittedMessageBase = namedtuple('TransmittedMessage',
                                     'value, transmission_delay, sender')


class TransmittedMessage(_TransmittedMessageBase):

    def __new__(cls, value, transmission_delay, sender=None):
        return super(TransmittedMessage, cls).__new__(
            cls, value, transmission_delay, sender
        )


def make_transmission_delay(transmission_speed: int, msg_length: int) -> int:
    return msg_length // transmission_speed + 1
