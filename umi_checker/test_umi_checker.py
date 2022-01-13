#!/usr/bin/env python3

"""Test for lossy counting and the UMI checker thingy.
"""

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from umi_checker.umi_checker import NormalCounter, cov, LossyCounter
import random

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

    def tearDown(self):
        pass

    ### THE TESTS ###
    def test_NormalCounter(self):
        """Check my little counter compatibility wrapper.
        """
        nc = NormalCounter()

        self.assertEqual(nc.get_n(), 0)
        nc.add_count("foo")
        self.assertEqual(nc.get_n(), 1)
        self.assertEqual(nc.most_common(2), [("foo",1)])

        # Also if we add the item before running get_n (should make no difference)
        nc2 = NormalCounter()
        nc2.add_count("bar")
        self.assertEqual(nc2.get_n(), 1)
        self.assertEqual(nc2.most_common(2), [("bar",1)])

    def test_LossyCounter(self):

        # Counter depends on shuffle order so we fix the random seed to get a consistent result
        random.seed(0xdeadbeef)

        lcounter1 = LossyCounter()
        lcounter2 = LossyCounter()

        stream = ''
        # 11 letters to count, in geometrically increasing frequency
        for i, c in enumerate('abcdefghijk'):
            stream += c * (2 ** i)

        stream1 = list(stream)
        stream2 = list(stream)
        random.shuffle(stream2)

        for c in stream1:
            lcounter1.add_count(c)
        for c in stream2:
            lcounter2.add_count(c)

        # mc1 counts the stream unshuffled, mc2 counts the same shuffled
        mc1 = lcounter1.most_common(10)
        mc2 = lcounter2.most_common(10)

        # The counter should have been created with default _epsilon of 5e-3
        self.assertEqual(lcounter1._epsilon, 5e-3)
        # And thus should not be confident of counting more than 7 values,
        # but with some shuffle orders it delivers 8
        self.assertEqual(len(mc1), 7)
        self.assertIn(len(mc2), [7,8])

        # In fact, the 7th value is sus, but the first six should match.
        # Occasionally the 6th is off by one if you try different shuffle seeds.
        self.assertEqual(mc1[:6], mc2[:6])

        # Both counters should know they got len(stream) items
        self.assertEqual(len(stream), (2 ** 11) - 1)
        self.assertEqual(lcounter1.get_n(), len(stream))
        self.assertEqual(lcounter2.get_n(), len(stream))

    def test_cov(self):

        # Cov is a simple, pure function
        self.assertEqual(cov([6,6,6]), 0.0)
        self.assertAlmostEqual(cov([1,2,3,4,5,6,7,8,9]), 0.54772256)

        # We fix some values by definition
        self.assertEqual(cov([]), 0.0)
        self.assertEqual(cov([6]), 0.0)

if __name__ == '__main__':
    unittest.main()
