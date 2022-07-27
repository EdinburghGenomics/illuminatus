#!/usr/bin/env python3

"""Test for stats_json_aggregator.py script
"""

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/stats_json_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from stats_json_aggregator import main as sja_main

class DummyArgs(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

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

    ### THE TESTS ###
    def test_on_example_1(self):

        args = DummyArgs(json = [DATA_DIR + "/Stats.no10x.json"])

        res = sja_main(args)

        self.assertEqual(list(res), [1])
        self.assertEqual( dict(res[1]),
                          { 'Assigned Reads': 10287288,
                            'Barcode Balance': 0.5933089459175601,
                            'Fraction Assigned': 0.7201743995564405,
                            'Fraction Assigned Raw': None,
                            'Fraction PF': 0.8053092035809595,
                            'Mean Reads Per Sample': 201711.5294117647,
                            'Number of Indexes': 51,
                            'Total Reads Raw': 14284440,
                            'Unassigned Reads PF': 1216103 } )

if __name__ == '__main__':
    unittest.main()
