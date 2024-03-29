#!/usr/bin/env python3

import unittest
from . import encode, decode
from itertools import product


class HammingTest(unittest.TestCase):

    def test_no_errors(self):

        for i in range(1 << 11):
            encoded = encode(i)
            errors, decoded = decode(encoded)
            self.assertEqual((0, i), (errors.value, decoded))

    def test_one_error(self):

        for error_position in range(11):

            for i in range(1 << 11):

                encoded = encode(i)

                encoded ^= 1 << error_position

                errors, decoded = decode(encoded)
                self.assertEqual((1, i), (errors.value, decoded))

    def test_two_errors(self):

        for error_pos_1, error_pos_2 in product(range(11), range(11)):

            if error_pos_1 == error_pos_2:
                continue

            for i in range(1 << 11):

                encoded = encode(i)

                encoded ^= (1 << error_pos_1) | (1 << error_pos_2)

                errors, decoded = decode(encoded)
                self.assertEqual(2, errors.value)


if __name__ == '__main__':
    unittest.main()
