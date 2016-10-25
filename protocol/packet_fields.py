from typing import Optional


class FixedSizeInt:

    def __init__(self, max_size, init_value: Optional[int]=0, optional=False):

        self.__max_size = max_size  # type: int
        self.__optional = optional  # type: bool
        self.__validate(init_value)
        self.__value = init_value   # type: Optional[int]

    def __get__(self, instance, owner):
        return self.__value

    def __set__(self, instance, value):
        self.__validate(value)
        self.__value = value

    def __validate(self, value):

        if value is None:
            if not self.__optional:
                raise ValueError("Value can't be None")
        elif value.bit_length() > self.__max_size:
            raise ValueError("Integer too big for this field")


class FlagField:

    def __init__(self, container_name, roffset):
        self.container_name = container_name
        self.mask = 1 << roffset

    def __get__(self, instance, owner):
        return bool(getattr(instance, self.container_name) & self.mask)

    def __set__(self, instance, value):
        new_val = getattr(instance, self.container_name)

        if value:
            new_val |= self.mask
        else:
            new_val &= ~self.mask

        setattr(instance, self.container_name, new_val)


class DataField:

    def __init__(self, container_name, roffset, length):
        self.container_name = container_name
        self.roffset = roffset
        self.mask = (1 << length) - 1

    def __get__(self, instance, owner):
        return ((getattr(instance, self.container_name) >> self.roffset)
                & self.mask)

    def __set__(self, instance, value):

        if self.mask.bit_length() < value.bit_length():
            raise ValueError('int too big for this field')

        container_name = self.container_name
        roffset = self.roffset

        old_container = (getattr(instance, container_name)
                         & ~(self.mask << roffset))
        setattr(instance, container_name, (value << roffset) | old_container)
