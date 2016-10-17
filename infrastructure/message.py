import typing


class _CollisionSentinel:
    def __repr__(self):
        return '<CollidedMessage>'


CollisionSentinel = _CollisionSentinel()
del _CollisionSentinel


TransmittedMessage = typing.NamedTuple('Message', [('value', typing.Any),
                                                   ('transmission_delay', int)])


def make_transmission_delay(transmission_speed: int, msg_length: int) -> int:
    return msg_length // transmission_speed + 1
