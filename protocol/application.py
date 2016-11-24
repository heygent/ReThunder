import abc
from typing import Any, Tuple


class Application(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def message_received(self, content: Any, length: int) -> Tuple[Any, int]:
        raise NotImplementedError


class DefaultApplication(Application):
    def message_received(self, content: Any, length: int):
        return None, 0
