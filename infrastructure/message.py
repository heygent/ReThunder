from collections import namedtuple


class _CollisionSentinel:
    def __repr__(self):
        return '<CollidedMessage>'


CollisionSentinel = _CollisionSentinel()
del _CollisionSentinel


TransmittedMessage = namedtuple('TransmittedMessage',
                                'value, transmission_delay, sender')


def make_transmission_delay(transmission_speed: float, msg_length: int) -> int:
    return max(int(msg_length / transmission_speed), 1)
