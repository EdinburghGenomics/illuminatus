#!/usr/bin/env python3

"""CHANGEME: Template/boilerplate for writing new test classes"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

"from scriptname import funcname"

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
    def test_1(self):
        self.assertEqual(True, True)

        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
