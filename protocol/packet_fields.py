from typing import Optional, List, Tuple, Any


class FixedSizeInt:

    def __init__(self, max_bits, init_value: Optional[int]=0, optional=False):

        self.max_bits: int = max_bits
        self.__optional: bool = optional
        self.__validate(init_value)
        self.__value: Optional[int] = init_value

    def __get__(self, instance, owner):
        return self.__value

    def __set__(self, instance, value):
        self.__validate(value)
        self.__value = value

    def __validate(self, value):

        if value is None:
            if not self.__optional:
                raise ValueError("Value can't be None")
        elif value.bit_length() > self.max_bits:
            raise ValueError("Integer too big for this field")


