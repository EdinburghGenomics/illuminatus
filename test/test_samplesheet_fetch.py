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
        #Always make a fresh temporary folder to be working in
        oldcwd = os.getcwd()
        temp_dir = mkdtemp()
        os.chdir(temp_dir)

        def cleanup():
            os.chdir(oldcwd)
            rmtree(temp_dir)

        self.addCleanup(cleanup)

        self.last_stdout = self.last_stderr = None

    def tearDown(self):
        #Cleanup of temp_dir is handled by the callback hook above
        pass

    def test_replace_original(self):
        """When this script sees the run folder for the first time.
        """

        touch('SampleSheet.csv')

        self.run_fetch()

        self.assertTrue(os.path.exists('SampleSheet.csv.0'))
        self.assertEqual(os.readlink('SampleSheet.csv'), 'SampleSheet.csv.0')

        self.assertEqual(self.last_stdout[0], "SampleSheet.csv renamed as SampleSheet.csv.0")

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
