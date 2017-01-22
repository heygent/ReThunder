
class FixedSizeInt:

    def __init__(self, name, max_bits):
        self.name = name
        self.max_bits = max_bits

    def __get__(self, instance, owner):
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        self._validate(value)
        instance.__dict__[self.name] = value

    def _validate(self, value):
        if value.bit_length() > self.max_bits:
            raise ValueError("Integer too big for this field")

