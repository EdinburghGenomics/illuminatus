#!/usr/bin/env python3
import unittest
import sys, os

from tempfile import mkdtemp
from shutil import rmtree, copytree
import subprocess
import time

"""This Python tool grabs updated sample sheets from the LIMS. It does this simply
   by looking for matching files in the SMB share.
   It's also responsible for renaming the original samplesheet saved out by the
   sequencer.
"""
#We're testing a shell script here.
from bashmocker import BashMocker
VERBOSE = os.environ.get('VERBOSE', '0') != '0'
FETCH = os.path.abspath(os.path.dirname(__file__) + '/../samplesheet_fetch.sh')

class T(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

        #Always make a fresh temporary folder to be working in
        oldcwd = os.getcwd()
        temp_dir = mkdtemp()
        os.chdir(temp_dir)

        def cleanup():
            os.chdir(oldcwd)
            rmtree(temp_dir)

        self.bm = BashMocker('RunStatus.py')

        if os.environ.get("KEEPTMP"):
            print("Temp dir = " + temp_dir, file=sys.stderr)
            print("Binmocker = " + self.bm.mock_bin_dir, file=sys.stderr)
        else:
            self.addCleanup(cleanup)
            self.addCleanup(self.bm.cleanup)

        #The script will find sample sheets in here...
        self.ss_dir = "fs_root/samplesheets_bcl2fastq_format"
        with open('genologics.conf', 'x') as cfh:
            print("SAMPLESHEETS_ROOT=" + os.path.realpath(self.ss_dir), file=cfh)
        os.makedirs(self.ss_dir)

        #The flowcell ID will always be XXXX
        self.environment = dict(
                FLOWCELLID = 'XXXX',
                GENOLOGICSRC = temp_dir + '/genologics.conf' )

    def bm_run_fetch(self, expected_retval=0):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs FETCH and returns STDOUT split into an array.
           (You can always examine self.bm.last_stderr directly)
        """
        retval = self.bm.runscript(FETCH, set_path=True, env=self.environment)

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

    def tearDown(self):
        #Cleanup of temp_dir is handled by the callback hook above
        pass

    def test_replace_original(self):
        """When this script sees the run folder for the first time,
           and there is a replacement available.
        """
        #Create a couple of candiate sample sheets.
        touch('SampleSheet.csv')
        touch(self.ss_dir + '/foo_XXXX.csv')
        touch(self.ss_dir + '/bar_XXXX.csv', 'this one')

        last_stdout = self.bm_run_fetch()

        self.assertTrue(os.path.isfile('SampleSheet.csv.0'))
        self.assertTrue(os.path.isfile('SampleSheet.csv.1'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.1')

        self.assertEqual(last_stdout[0], "SampleSheet.csv renamed as SampleSheet.csv.0")
        self.assertEqual(last_stdout[2], "SampleSheet.csv for XXXX is now linked to new SampleSheet.csv.1")

        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'this one')

        # And go again. This should do nothing.
        touch(self.ss_dir + '/bad_YXXXX.csv', 'ignore this one')
        last_stdout = self.bm_run_fetch()
        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'this one')

        # And again. This should give us .2
        touch(self.ss_dir + '/baz_XXXX.csv', 'final one')
        last_stdout = self.bm_run_fetch()
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.2')
        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'final one')


    def test_keep_original(self):
        """When this script sees the run folder for the first time,
           and there is no replacement available.
        """
        touch('SampleSheet.csv')

        last_stdout = self.bm_run_fetch()

        self.assertTrue(os.path.exists('SampleSheet.csv.0'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')

        self.assertEqual(last_stdout[0], "SampleSheet.csv renamed as SampleSheet.csv.0")
        self.assertEqual(last_stdout[1][:36], "No candidate replacement samplesheet")


    def test_none_found(self):
        """This shouldn't happen in practise. May want to reconsider the behaviour
           of the script?
        """
        last_stdout = self.bm_run_fetch()

        self.assertTrue(os.path.exists('SampleSheet.csv.0'))
        self.assertEqual(os.stat('SampleSheet.csv.0').st_size, 0)
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')

        self.assertEqual(last_stdout[0], "SampleSheet.csv.0 created as empty file")

    def test_not_a_link(self):
        """This shouldn't happen, but it did when RSYNC clobbered the symlink, so
           I want to account for it. If SampleSheet.csv is a file but SampleSheet.csv.0
           exists then the script should check they are identical and deal with it.
        """
        touch('SampleSheet.csv', 'original')
        touch('SampleSheet.csv.0', 'original')

        last_stdout = self.bm_run_fetch()

        # The link should be restored.
        self.assertTrue(os.path.exists('SampleSheet.csv.0'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')
        self.assertFalse(os.path.exists('SampleSheet.csv.bak'))

        os.unlink('SampleSheet.csv')
        touch('SampleSheet.csv', 'mismatch')
        touch('SampleSheet.csv.1', 'mismatch')

        last_stdout = self.bm_run_fetch()

        # The script should link it to .1 instead
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.1')

        os.unlink('SampleSheet.csv')
        touch('SampleSheet.csv', 'mismatch2')

        # But this should just fail and the file should stay in place
        self.bm_run_fetch(1)

        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'mismatch2')

    def test_override_old(self):
        """For testing, or if for some reason we need to amend the samplesheet outside
           of the LIMS, we want to ensure that SampleSheet.csv.OVERRIDE gets priority.
           But the file now needs to be under the pipeline directory.
        """
        touch('SampleSheet.csv', 'original')
        touch('SampleSheet.csv.OVERRIDE', 'override')
        touch(self.ss_dir + '/foo_XXXX.csv', 'ignore this')

        last_stdout = self.bm_run_fetch(expected_retval=1)

        # At this point we should be left with SampleSheet.csv renamed to
        # SampleSheet.csv.0 and symlinked.
        self.assertTrue(os.path.isfile('SampleSheet.csv.0'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')
        self.assertEqual(last_stdout[2], "Please move SampleSheet.csv.OVERRIDE to the pipeline subdir then redo lanes.")

    def test_override(self):
        """For testing, or if for some reason we need to amend the samplesheet outside
           of the LIMS, we want to ensure that pipeline/SampleSheet.csv.OVERRIDE gets priority.
        """
        touch('SampleSheet.csv', 'original')
        os.mkdir('pipeline')
        touch('pipeline/SampleSheet.csv.OVERRIDE', 'override')
        touch(self.ss_dir + '/foo_XXXX.csv', 'ignore this')

        last_stdout = self.bm_run_fetch()

        # So the original SS still gets moved aside, but the link goes to
        # override and the alternative in ss_dir is ignored.
        self.assertTrue(os.path.isfile('SampleSheet.csv.0'))
        self.assertFalse(os.path.isfile('SampleSheet.csv.1'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'pipeline/SampleSheet.csv.OVERRIDE')
        self.assertEqual(last_stdout[1], "Giving priority to pipeline/SampleSheet.csv.OVERRIDE.")

    def test_no_flowcellid(self):
        """If no flowcell ID is provided, the script should attempt to get one by running
           RunStatus.py and then fail if none is obtained.
        """
        touch('SampleSheet.csv')
        del(self.environment['FLOWCELLID'])

        last_stdout = self.bm_run_fetch(expected_retval=1)

        self.assertEqual(last_stdout[0], "No FLOWCELLID was provided, and obtaining one from RunStatus.py failed.")

        #The script should have attempted to call RunStatus.py just once.
        expected_calls = self.bm.empty_calls()
        expected_calls['RunStatus.py'] = [[]]
        self.assertEqual(self.bm.last_calls, expected_calls)

    def test_always_touch(self):
        """Check that the SampleSheet.csv symlink is touch'd, even if everything else
           is a no-op.
        """
        touch('SampleSheet.csv')
        touch(self.ss_dir + '/bar_XXXX.csv', 'this one')

        first_stdout = self.bm_run_fetch()

        utimestamp = time.time()

        # Assumes we have millisecond timestamps on the files. If not, these and
        # other tests will fail.
        self.assertLess(os.lstat('SampleSheet.csv').st_mtime, utimestamp)

        # Run the thingy again
        time.sleep(0.1)
        second_stdout = self.bm_run_fetch()
        self.assertEqual(second_stdout[0], "SampleSheet.csv for XXXX is already up-to-date")
        self.assertGreater(os.lstat('SampleSheet.csv').st_mtime, utimestamp)

    def test_case_mismatch(self):
        """Test still fetching the sample sheet even when the case mismatches,
           since this seems to be a thing with the new MiSeq software.
        """
        #Create a couple of candiate sample sheets.
        touch('SampleSheet.csv')
        touch(self.ss_dir + '/foo_jd7l6.csv')
        touch(self.ss_dir + '/bar_JD7L6.csv', 'this one')

        self.environment['FLOWCELLID'] = 'jd7l6'
        last_stdout = self.bm_run_fetch()

        self.assertTrue(os.path.isfile('SampleSheet.csv.0'))
        self.assertTrue(os.path.isfile('SampleSheet.csv.1'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.1')

        self.assertEqual(last_stdout[0], "SampleSheet.csv renamed as SampleSheet.csv.0")
        self.assertEqual(last_stdout[2], "SampleSheet.csv for jd7l6 is now linked to new SampleSheet.csv.1")

        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'this one')

def touch(filename, contents="touch"):
    with open(filename, 'x') as fh:
        print(contents, file=fh)

    # If we don't have high-resolution timestamps on $TMPDIR then we need:
    # time.sleep(1)

if __name__ == '__main__':
    unittest.main()
