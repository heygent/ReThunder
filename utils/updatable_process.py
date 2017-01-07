from typing import Any, List, Optional

import simpy
import abc

from utils.run_process_decorator import run_process


class UpdatableProcess(metaclass=abc.ABCMeta):

    def __init__(self, env: simpy.Environment):

        self.env: simpy.Environment = env
        self._update_ev: simpy.Event = env.event()
        self._stop_ev: simpy.Event = None
        self._start_time: Optional[int] = None

        self.__running_process: simpy.Process = None

    @run_process
    def __run_proc(self, init_value: List[Any]):

        if len(init_value) > 1:
            self._update_ev.succeed(init_value[1:])

        self._on_start(init_value[0])

        if not isinstance(self._stop_ev, simpy.Event):
            raise ValueError(
                "self._stop_ev in an UpdatableProcess must be set to an event "
                "during _on_start()"
            )

        self._start_time = self.env.now

        while True:

            yield self.env.any_of((self._stop_ev, self._update_ev))
            yield self.env.timeout(0)

            if self._stop_ev.processed and self._update_ev.processed:

                self.__running_process = self.__run_proc(self._update_ev.value)

                self._update_ev = self.env.event()
                return self._on_stop(self._stop_ev.value)

            elif self._update_ev.processed:

                for elem in self._update_ev.value:
                    self._on_update(elem)

                self._update_ev = self.env.event()

            elif self._stop_ev.processed:

                self.__running_process = None
                return self._on_stop(self._stop_ev.value)

            else:
                assert False, "Spurious wake"

    @abc.abstractmethod
    def _on_start(self, init_value):
        raise NotImplementedError

    @abc.abstractmethod
    def _on_update(self, update_value):
        raise NotImplementedError

    @abc.abstractmethod
    def _on_stop(self, stop_value):
        raise NotImplementedError

    @property
    def _running(self):
        return self.__running_process is not None

    def update(self, value):

        if self.__running_process is None:
            self.__running_process = self.__run_proc([value])

        elif self._update_ev.triggered:
            self._update_ev.value.append(value)

        else:
            self._update_ev.succeed([value])
