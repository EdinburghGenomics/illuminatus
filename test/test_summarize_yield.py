#!/usr/bin/env python3

"""Test the summarize_yield.py script. I'm not going to test that parts that use the
   InterOP libraries but I'll test the data reformatting code.
"""

import sys, os, re
import unittest
import logging
import yaml

from sandbox import TestSandbox
from unittest.mock import Mock
from pprint import pprint

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/summarize_yield')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

# Allow the functions to be loaded without having the interop modules installed.
sys.modules.update( { 'interop': Mock() } )

from summarize_yield import main as summarize_yield_main

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        self.maxDiff = None

        # We need a temporary directory for outputz
        self.tmp_dir = TestSandbox()

    def tearDown(self):
        self.tmp_dir.cleanup()

    ### THE TESTS ###
    def test_1(self):
        """Test the formatting logic with a sample run.
           Note that the example was generated with the script so this is only a regression
           test.
        """
        example = "220812_A00291_0454_AHCGK2DMXY"

        # Run summarize_yield_main to save MQC files in self.tmp_dir
        summarize_yield_main( run_dir = f"{DATA_DIR}/{example}_yield.yaml",
                              out_dir = self.tmp_dir.sandbox,
                              always_dump = False )

        # Re-running should be fine and produce no warnings
        summarize_yield_main( run_dir = f"{DATA_DIR}/{example}_yield.yaml",
                              out_dir = self.tmp_dir.sandbox,
                              always_dump = False )

        # Check the files are as expected
        self.assertEqual( self.tmp_dir.lsdir('.'),
                          ['lane1/', 'lane2/', 'overview/'] )

        # Check the content is as expected. Do this by loading the YAML data
        # rather than just diffing the files.
        for adir in self.tmp_dir.lsdir('.'):
            adir = adir.rstrip('/')

            fname = f"{adir}/summarize_yield_{adir}_mqc.yaml"
            with open(f"{DATA_DIR}/{example}_expected/{fname}") as yfh:
                expected_res = yaml.safe_load(yfh)
            with open(f"{self.tmp_dir.sandbox}/{fname}") as yfh:
                got_res = yaml.safe_load(yfh)

            if VERBOSE:
                print(f"Comparing {yfh.name}:")
                pprint(got_res)

            self.assertEqual(expected_res, got_res)

if __name__ == '__main__':
    unittest.main()
