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

