#!/usr/bin/env python3

"""Template/boilerplate for writing new test classes"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging
import time, datetime
from glob import glob

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'
AUTO_REDO = os.path.abspath(os.path.dirname(__file__) + '/../auto_redo.sh')
BIN_PATH = os.path.abspath(os.path.dirname(__file__) + '/..')

# My little test helpers
from binmocker import BinMocker
from sandbox import TestSandbox

class T(unittest.TestCase):

    def setUp(self):
        # We want a sandbox version of DATA_DIR (playing /lustre/seqdata)
        self.seqdata = TestSandbox(DATA_DIR)
        self.addCleanup(self.seqdata.cleanup)

        # Need to get the directory format right!
        self.thismonth = datetime.date.today().strftime('%Y/%-m')

        # We also want a second sandbox where we can create sample sheets
        self.sheets = TestSandbox()
        self.addCleanup(self.sheets.cleanup)
        self.sheets.make(self.thismonth+'/')

        # We want a binmocker as a conveneint way to run the script,
        # though nothing is actually mocked out
        self.bm = BinMocker()

        # Show the script where to look for the sheets (long-windedly)
        self.sheets_dir = os.path.join(self.sheets.sandbox, self.thismonth)
        self.sheets.make( 'genologics.conf', content="SAMPLESHEETS_ROOT={}".format(self.sheets.sandbox) )
        self.environment = dict(
                PATH = BIN_PATH + ':' + os.environ['PATH'],
                SEQDATA_LOCATION = self.seqdata.sandbox,
                GENOLOGICSRC = os.path.join( self.sheets.sandbox, 'genologics.conf' ) )

        # Grab the current time (after copying everything)
        self.unixtime = time.time()

    def bm_run_redo(self, expected_retval=0):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs auto_redo.sh and captures the output.
           (You can always examine self.bm.last_stderr directly)
        """
        retval = self.bm.runscript(AUTO_REDO, set_path=True, env=self.environment)

        #Where a file is missing it's always useful to see the error.
        #(status 127 is the standard shell return code for a command not found)
        if retval == 127 or VERBOSE:
            print("STDERR:")
            print(self.bm.last_stderr)
        if VERBOSE:
            print("STDOUT:")
            print(self.bm.last_stdout)

        self.assertEqual(retval, expected_retval)

        return self.bm.last_stdout.split("\n")

    ### THE TESTS ###
    def test_noop(self):
        """With nothing in self.sheets_dir the script should do nothing.
        """
        self.bm_run_redo()

        # TODO - check the STDOUT

        # See no pipelines were touched
        for pd in glob(self.seqdata.sandbox + '/*_*_*_*/pipeline'):
            self.assertTrue( os.lstat(pd).st_mtime < self.unixtime )


if __name__ == '__main__':
    unittest.main()
