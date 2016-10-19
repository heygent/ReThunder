#!/usr/bin/env python3

import unittest
import wrappers as hamming
from itertools import product


class HammingTest(unittest.TestCase):

    def test_no_errors(self):

        for i in range(1 << 11):
            encoded = hamming.encode(i)
            errors, decoded = hamming.decode(encoded)
            self.assertEqual((0, i), (errors.value, decoded))

    def test_one_error(self):

        for error_position in range(11):

            for i in range(1 << 11):

                encoded = hamming.encode(i)

                encoded ^= 1 << error_position

                errors, decoded = hamming.decode(encoded)
                self.assertEqual((1, i), (errors.value, decoded))

    def test_two_errors(self):

        for error_position_1, error_position_2 in product(range(11), range(11)):

            if error_position_1 == error_position_2:
                continue

            for i in range(1 << 11):

                encoded = hamming.encode(i)

                encoded ^= (1 << error_position_1) | (1 << error_position_2)

                errors, decoded = hamming.decode(encoded)
                self.assertEqual(2, errors.value)


if __name__ == '__main__':
    unittest.main()
