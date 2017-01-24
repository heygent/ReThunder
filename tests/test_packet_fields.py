import unittest
from protocol.packet_fields import FixedSizeInt


class SomePacket:
    id1 = FixedSizeInt(8)
    id2 = FixedSizeInt(2)
    flag = FixedSizeInt(1)


class TestPacketFields(unittest.TestCase):

    def test1(self):
        x = SomePacket()

        x.id1 = 15
        x.id2 = 3
        x.flag = 0

        with self.assertRaises(ValueError):
            x.id2 = 5

        x.id2 = 1
        x.id1 = 140

        with self.assertRaises(ValueError):
            x.flag = 1000

        self.assertEquals((x.id1, x.id2, x.flag), (140, 1, 0))




