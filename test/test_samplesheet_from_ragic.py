#!/usr/bin/env python3

"""Test for the gen_ss function in test_samplesheet_from_ragic.py
"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging
import json

DATA_DIR = f"{os.path.abspath(os.path.dirname(__file__))}/ragic_sample_sheets"
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from samplesheet_from_ragic import gen_ss

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
    def test_no_samples(self):
        """What if the run has no samples added to any of the lanes?
        """
        with open(f"{DATA_DIR}/LP3YP/run_LP3YP_empty.json") as jfh:
            run = json.load(jfh)

        # If there is nothing in the run this should raise an exception.
        # In fact, if there are missing lanes this should raise an exception.
        self.assertRaises(RuntimeError, gen_ss, run)

    def test_gen_ss(self):
        """The JSON data has been fetched from ragic using the --save option in
           samplesheet_from_ragic.py
        """
        with open(f"{DATA_DIR}/LP3YP/run_LP3YP.json") as jfh:
            run = json.load(jfh)

        with open(f"{DATA_DIR}/LP3YP/K001_LP3YP_SampleSheet.csv") as cfh:
            expected_lines = [ l.rstrip("\n") for l in cfh ]

        generated_lines = list(gen_ss(run))

        # The dates will differ, so mask them out
        for linelist in [generated_lines, expected_lines]:
            for i in range(len(linelist)):
                if linelist[i].startswith("Date,"):
                    linelist[i] = "Date,MASKED"

        self.assertEqual(generated_lines, expected_lines)

if __name__ == '__main__':
    unittest.main()
