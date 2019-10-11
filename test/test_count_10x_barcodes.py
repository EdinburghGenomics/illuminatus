#!/usr/bin/env python3

"""Test that I can detect (or guess) 10x lanes"""

import sys, os, re
import unittest
from unittest.mock import patch
from io import StringIO
import logging
from collections import namedtuple

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/stats_json_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

try:
    # This is a safe way to manipulate sys.path without impacting later tests.
    with patch('sys.path', new=['.'] + sys.path):
        from count_10x_barcodes import main as count_main
except:
    #If this fails, you is probably running the tests wrongly
    print("****",
          "To test your working copy of the code you should use the helper script:",
          "  ./run_tests.sh count_10x_barcodes",
          "or to run all tests, just",
          "  ./run_tests.sh",
          "****",
          sep="\n")
    raise

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

        # Make an object to hold the args
        self.args = namedtuple("args", ['verbose', 'json'])(
                                                verbose = False,
                                                json = [] )

    def setargs(self, **kwargs):
        self.args = self.args._replace(**kwargs)

    ### THE TESTS ###
    def test_nop(self):
        """The ArgumentParser prevents callign the script with no files and forcing this
           results in a ValueError.
        """
        self.assertRaises(ValueError, count_main, self.args)

    def test_positive(self):
        """All the files that should flag as 10x"""

        pos_files = "atac10x with10x2 with10x".split()
        for f in pos_files:
            self.setargs(json = [ "{}/Stats.{}.json".format(DATA_DIR, f) ])
            self.assertTrue(count_main(self.args), *self.args.json)

        # And all together
        self.setargs( json = [ "{}/Stats.{}.json".format(DATA_DIR, f) for f in pos_files ] )
        self.assertTrue(count_main(self.args))


    def test_negative(self):
        """All the files that should NOT flag as 10x"""

        neg_files = "no10x no10x2".split()
        for f in neg_files:
            self.setargs(json = [ "{}/Stats.{}.json".format(DATA_DIR, f) ])
            self.assertFalse(count_main(self.args), *self.args.json)

        # And all together
        self.setargs(json = [ "{}/Stats.{}.json".format(DATA_DIR, f) for f in neg_files ])
        self.assertFalse(count_main(self.args))

    @patch('sys.stdout', new_callable=StringIO)
    def test_all(self, dummy_stdout):
        """All the files together, and also testing the verbose flag"""
        all_files = "atac10x with10x2 with10x".split() + "no10x no10x2".split()

        self.setargs(json = [ "{}/Stats.{}.json".format(DATA_DIR, f) for f in all_files ])
        self.assertTrue(count_main(self.args))
        self.assertEqual(dummy_stdout.getvalue(), '')

        self.setargs(verbose = True)
        self.assertTrue(count_main(self.args))
        self.assertTrue(dummy_stdout.getvalue().endswith('Max found: 64\n'))
        self.assertEqual( len(dummy_stdout.getvalue().rstrip().split('\n')),
                          (3*len(self.args.json)) + 1 )

if __name__ == '__main__':
    unittest.main()
