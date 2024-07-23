#!/usr/bin/env python3

"""Test the auto-redo. Most of the logic here is to ensure it doesn't auto-redo
   when it's not safe to do so.
"""

import sys, os, re
import unittest
import logging
import time, datetime
from glob import glob
import shutil

SEQDATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/auto_redo_seqdata')
NEWSHEETS_DIR = os.path.abspath(os.path.dirname(__file__) + '/auto_redo_newsheets')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'
AUTO_REDO = os.path.abspath(os.path.dirname(__file__) + '/../auto_redo.sh')
BIN_PATH = os.path.abspath(os.path.dirname(__file__) + '/..')

# My little test helpers
from bashmocker import BashMocker
from sandbox import TestSandbox

class T(unittest.TestCase):

    def setUp(self):
        # We want a sandbox version of DATA_DIR (playing /lustre/seqdata)
        self.seqdata = TestSandbox(SEQDATA_DIR)
        self.addCleanup(self.seqdata.cleanup)

        # Need to get the directory format right!
        self.thismonth = datetime.date.today().strftime('%Y/%-m')

        # We also want a second sandbox where we can create sample sheets
        self.sheets = TestSandbox()
        self.addCleanup(self.sheets.cleanup)
        self.sheets.make(self.thismonth+'/')

        # We want a binmocker as a conveneint way to run the script,
        # though nothing is actually mocked out
        self.bm = BashMocker()
        self.addCleanup(self.bm.cleanup)

        # Show the script where to look for the sheets (long-windedly)
        self.sheets_dir = os.path.join(self.sheets.sandbox, self.thismonth)
        self.sheets.make( 'genologics.conf', content="SAMPLESHEETS_ROOT={}".format(self.sheets.sandbox) )
        self.environment = dict(
                PATH = BIN_PATH + ':' + os.environ['PATH'],
                SEQDATA_LOCATION = self.seqdata.sandbox,
                VERBOSE = "1", # Note the VERBOSE fed to the script is not related to test verbosity!
                GENOLOGICSRC = os.path.join( self.sheets.sandbox, 'genologics.conf' ) )

        # Grab the current time (after copying everything)
        self.unixtime = time.time()

    def bm_run_redo(self, expected_retval=0, **env):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs auto_redo.sh and captures the output.
           (You can always examine self.bm.last_stderr directly)
        """
        combined_env = self.environment.copy()
        combined_env.update(env)
        retval = self.bm.runscript(AUTO_REDO, set_path=True, env=combined_env)

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
        """With nothing useful in self.sheets_dir the script should do nothing.
        """
        # Verbosely...
        res1 = self.bm_run_redo()
        self.assertEqual(res1[1], "Checking 0 files.")

        # Non-verbosely...
        res1q = self.bm_run_redo(VERBOSE="0")
        self.assertEqual(res1q[1], "")

        # Add a 3 day old sample sheet and a new one which does not relate
        # to any run, and a new one in another directory.
        self.sheets.make(self.thismonth + '/sheet_XXXX.csv', hours_age=72)
        self.sheets.make(self.thismonth + '/sheet_YYYY.csv', hours_age=2)
        self.sheets.make('2000/2/sheet_YYYY.csv', hours_age=2)

        res2 = self.bm_run_redo()
        self.assertEqual(res2[1], "Checking 1 files.")

        # See no pipelines were touched at any time
        for pd in glob(self.seqdata.sandbox + '/*_*_*_*/pipeline'):
            self.assertTrue( os.lstat(pd).st_mtime < self.unixtime )

        # Finally set HTLB to not pick up anything
        self.environment['REDO_HOURS_TO_LOOK_BACK'] = '1'
        res3 = self.bm_run_redo()
        self.assertEqual(res3[1], "Checking 0 files.")

    def test_restarts(self):
        """Test various runs that want to be restarted, or not.
           We can run these in one sweep.
        """
        # 1 - a run with a new sheet but bad status
        # 160726_K00166_0120_BHCVH2BBXX (reads_unfinished)

        # 2 - a run with a new sheet but SampleSheet.csv is newer
        # 150602_M01270_0108_000000000-ADWKV

        # 3 - a run with a new sheet and 1 lane to redo
        # 160614_K00368_0023_AHF724BBXX

        # 4 - a run with a new sheet and 2 lanes to redo
        # 160607_D00248_0174_AC9E4KANXX

        # 5 - a run with a new sheet and no changes(!)
        # 160603_M01270_0196_000000000-AKGDE

        # 6 - a failed run with a new sheet and 1 lane to redo,
        #     so we redo the whole thing anyway
        # 160606_K00166_0102_BHF22YBBXX

        # 7 - a failed run with a new sheet but SampleSheet.csv.OVERRIDE is present
        # 180430_M05898_0007_000000000-BR92R (not overridden)
        # 180430_M05898_0007_000000000-OVRID (identical with OVERRIDE)

        # For starters, make all the files in the sandbox 20 hours old
        self.seqdata.touch('.', hours_age=20, recursive=True)

        # These are in auto_redo_newsheets so copy them in. No need to update
        # the timestamps as copy() leaves all files with current mtime.
        for ns in glob(NEWSHEETS_DIR + '/*.csv'):
            shutil.copy(ns, self.sheets_dir, follow_symlinks=True)

        # Touch for #2 should make the new sheet too old.
        self.sheets.touch(self.thismonth + '/sheet_ADWKV.csv', hours_age=2)
        self.seqdata.touch('150602_M01270_0108_000000000-ADWKV/SampleSheet.csv')

        # Now run the whole shebang
        res1 = self.bm_run_redo()
        self.assertEqual(res1[1], "Checking 8 files.")

        # 1 should be untouched
        # ditto 2 and 5 and 7b
        for r in [ '160726_K00166_0120_BHCVH2BBXX',
                   '150602_M01270_0108_000000000-ADWKV',
                   '160603_M01270_0196_000000000-AKGDE',
                   '180430_M05898_0007_000000000-OVRID', ]:
            self.assertTrue( os.lstat(f"{self.seqdata.sandbox}/{r}/pipeline").st_mtime < self.unixtime )

        # The others (3 4 6 and 7a) should be modified
        for r in [ '160614_K00368_0023_AHF724BBXX',
                   '160607_D00248_0174_AC9E4KANXX',
                   '160606_K00166_0102_BHF22YBBXX',
                   '180430_M05898_0007_000000000-BR92R', ]:
            self.assertFalse( os.lstat(f"{self.seqdata.sandbox}/{r}/pipeline").st_mtime < self.unixtime )


        # 3 should have a redo on lane 8 only
        self.assertEqual( self.seqdata.lsdir('160614_K00368_0023_AHF724BBXX/pipeline', glob="*.redo"),
                          ['lane8.redo'] )

        # 4 should have 2 and 5 changed
        self.assertEqual( self.seqdata.lsdir('160607_D00248_0174_AC9E4KANXX/pipeline', glob="*.redo"),
                          ['lane2.redo', 'lane5.redo'] )

        # And 6 should have all 8 to redo because it was failed
        self.assertEqual( self.seqdata.lsdir('160606_K00166_0102_BHF22YBBXX/pipeline', glob="*.redo"),
                          ['lane{}.redo'.format(n) for n in '12345678'] )

        # Now go again
        unixtime2 = time.time()
        res2 = self.bm_run_redo()
        self.assertEqual(res2[1], "Checking 8 files.")

        # See no pipelines were touched this time
        for pd in glob(self.seqdata.sandbox + '/*_*_*_*/pipeline'):
            self.assertTrue( os.lstat(pd).st_mtime < unixtime2 )

    def test_space_in_filename(self):
        """See doc/bug_on_A00291_0218.txt
           It is indeed possible to get spaces etc. in the filenames.
        """
        # For starters, make all the files in the sandbox 20 hours old
        self.seqdata.touch('.', hours_age=20, recursive=True)

        # Now just copy in example 4 above - ie. for C9E4KANXX
        for ns in glob(NEWSHEETS_DIR + '/sheet_C9E4KANXX.csv'):
            shutil.copy(ns, self.sheets_dir, follow_symlinks=True)
            os.rename(self.sheets_dir + '/sheet_C9E4KANXX.csv',
                      self.sheets_dir + '/eat my sheet_C9E4KANXX.csv')

        # Now run the thing
        res1 = self.bm_run_redo()
        self.assertEqual(res1[1], "Checking 1 files.")

        # The appropriate run should have 2 and 5 changed
        self.assertEqual( self.seqdata.lsdir('160607_D00248_0174_AC9E4KANXX/pipeline', glob="*.redo"),
                          ['lane2.redo', 'lane5.redo'] )

    def test_case_mismatch(self):
        """Looking at run 201113_M01270_0137_jd7l6 it seems we can get a case mismatch
           in the flowcell name. This may be a quirk of the upgraded software. I'm not sure
           if it signigfies something specific?
        """
        # Rename the 180430_M05898_0007_000000000-BR92R run
        os.rename( self.seqdata.sandbox + '/180430_M05898_0007_000000000-BR92R',
                   self.seqdata.sandbox + '/180430_M05898_0007_br92r' )
        # Now make all the files in the sandbox 20 hours old
        self.seqdata.touch('.', hours_age=20, recursive=True)

        # Now copy in the replacement sheet
        shutil.copy(NEWSHEETS_DIR + '/sheet_BR92R.csv', self.sheets_dir, follow_symlinks=True)

        # Now run the thing
        res1 = self.bm_run_redo()
        self.assertEqual(res1[1], "Checking 1 files.")

        # We should be redoing the run.
        self.assertEqual( self.seqdata.lsdir('180430_M05898_0007_br92r/pipeline', glob="*.redo"),
                          ['lane1.redo'] )

if __name__ == '__main__':
    unittest.main()
