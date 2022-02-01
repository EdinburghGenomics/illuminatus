#!/usr/bin/env python3

"""Test the script that examines the early demultiplex barcode check
"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging
from glob import glob

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/read1_qc_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from assess_bc_check import main as check_main, load_stats

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

    def get_ex(self, runid, lane_pattern="lane*"):
        # Return a list of all the Stats.json file in a given example
        return glob(os.path.join(DATA_DIR, runid, 'QC/bc_check', lane_pattern, 'Stats/Stats.json'))

    ### THE TESTS ###
    def test_good(self):
        """These examples are good and should produce no output
        """
        ex1 = self.get_ex('171019_A00291_0005_AH57MVDMXX')
        self.assertEqual(check_main(ex1), [])

        ex2 = self.get_ex('220113_A00291_0410_AHV23HDRXY', 'lane1')
        self.assertEqual(check_main(ex2), [])

    def test_bad(self):
        """This one is a problem
        """
        expected_res = [
            'Problem in lane 2:',
            'Project 21360 has only 14901 total reads, compared to 416186 unassigned.',
            '',
            'Barcode mismatch level was set to 1 for this lane.',
            '',
            'Top unassigned codes. See the HTML report for the full list...',
            '---',
            'foo',
            'bar',
            'baz',
            '---' ]

        ex1 = self.get_ex('220113_A00291_0410_AHV23HDRXY')
        self.assertEqual(check_main(ex1), expected_res)

        # Should be the same if we just look at lane 2
        ex2 = self.get_ex('220113_A00291_0410_AHV23HDRXY', 'lane2')
        self.assertEqual(check_main(ex2), expected_res)

if __name__ == '__main__':
    unittest.main()
