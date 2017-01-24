from collections import defaultdict


class FixedSizeInt:
    """
    Descrittore che controlla la lunghezza in bit dei valori con cui viene
    settata la proprietà, e che causa ValueError se questi sono più lunghi del
    valore stabilito alla creazione.
    """

    def __init__(self, max_bits):
        self._data = defaultdict(int)
        self.max_bits = max_bits

    def __get__(self, instance, owner):
        return self._data[instance]

    def __set__(self, instance, value):

        if not isinstance(value, int):
            raise TypeError("Value must be int")

        if value.bit_length() > self.max_bits:
            raise ValueError("Integer too big for this field")

        self._data[instance] = value
