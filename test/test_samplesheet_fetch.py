#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os

from tempfile import mkdtemp
from shutil import rmtree, copytree
import subprocess

#We're testing a shell script here.
FETCH = os.path.abspath(os.path.dirname(__file__) + '/../samplesheet_fetch.sh')

"""This Python tool grabs updated sample sheets from the LIMS. It does this simply
   by looking for matching files in the SMB share.
   It's also responsible for renaming the original samplesheet saved out by the
   sequencer.
"""

class TestSamplesheetFetch(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

        #Always make a fresh temporary folder to be working in
        oldcwd = os.getcwd()
        temp_dir = mkdtemp()
        os.chdir(temp_dir)

        def cleanup():
            os.chdir(oldcwd)
            rmtree(temp_dir)

        if os.environ.get("KEEPTMP"):
            print(temp_dir)
        else:
            self.addCleanup(cleanup)

        self.last_stdout = self.last_stderr = None

        #The script will find sample sheets in here...
        self.ss_dir = "fs_root/samplesheets_bcl2fastq_format"
        with open('genologics.conf', 'x') as cfh:
            print("FS_ROOT=" + temp_dir + "/fs_root", file=cfh)
        os.makedirs(self.ss_dir)
        os.environ['GENOLOGICSRC'] = temp_dir + '/genologics.conf'

        #The flowcell ID will always be XXXX
        os.environ['FLOWCELLID'] = 'XXXX'

    def tearDown(self):
        #Cleanup of temp_dir is handled by the callback hook above
        pass

    def test_replace_original(self):
        """When this script sees the run folder for the first time,
           and there is a replacement available.
        """

        touch('SampleSheet.csv')
        touch(self.ss_dir + '/foo_XXXX.csv')
        touch(self.ss_dir + '/bar_XXXX.csv', 'this one')

        self.run_fetch()

        self.assertTrue(os.path.isfile('SampleSheet.csv.0'))
        self.assertTrue(os.path.isfile('SampleSheet.csv.1'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.1')

        self.assertEqual(self.last_stdout[0], "SampleSheet.csv renamed as SampleSheet.csv.0")
        self.assertEqual(self.last_stdout[2], "SampleSheet.csv is now linked to new SampleSheet.csv.1")

        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'this one')

        # And go again. This should do nothing.
        touch(self.ss_dir + '/bad_YXXXX.csv', 'ignore this one')
        self.run_fetch()
        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'this one')

        # And again. This should give us .2
        touch(self.ss_dir + '/baz_XXXX.csv', 'final one')
        self.run_fetch()
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.2')
        with open("SampleSheet.csv") as fh:
            self.assertEqual(fh.read().rstrip(), 'final one')


    def test_keep_original(self):
        """When this script sees the run folder for the first time,
           and there is no replacement available.
        """
        touch('SampleSheet.csv')

        self.run_fetch()

        self.assertTrue(os.path.exists('SampleSheet.csv.0'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')

        self.assertEqual(self.last_stdout[0], "SampleSheet.csv renamed as SampleSheet.csv.0")
        self.assertEqual(self.last_stdout[1][:36], "No candidate replacement samplesheet")


    def test_none_found(self):
        """This shouldn't happen in practise. May want to reconsider the behaviour
           of the script?
        """

        self.run_fetch()

        self.assertTrue(os.path.exists('SampleSheet.csv.0'))
        self.assertEqual(os.stat('SampleSheet.csv.0').st_size, 0)
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')

        self.assertEqual(self.last_stdout[0], "SampleSheet.csv.0 created as empty file")

    def run_fetch(self):
        """Run the script. If this gets more complex I might use BinMocker from
           the driver test.
        """
        p = subprocess.Popen(FETCH, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE,
                             universal_newlines = True,
                             close_fds=True)

        last_stdout, last_stderr = p.communicate()
        self.last_stdout = last_stdout.split("\n")
        self.last_stderr = last_stderr.split("\n")

        self.assertEqual(p.returncode, 0)

def touch(filename, contents="touch"):
    with open(filename, 'x') as fh:
        print(contents, file=fh)

if __name__ == '__main__':
    unittest.main()
