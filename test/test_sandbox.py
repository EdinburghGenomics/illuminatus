#!/usr/bin/env python3

"""Test out the sandbox helper class."""

import sys, os, re
import unittest
import logging
import time

from sandbox import TestSandbox


DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/asandbox')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

try:
    sys.path.insert(0, '.')
    # from lib_or_script import functions
except:
    #If this fails, you is probably running the tests wrongly
    print("****",
          "To test your working copy of the code you should use the helper script:",
          "  ./run_tests.sh <name_of_test>",
          "or to run all tests, just",
          "  ./run_tests.sh",
          "****",
          sep="\n")
    raise

class T(unittest.TestCase):

    def setUp(self):
        # Most of the time the class will be used like this
        self.sb = TestSandbox(DATA_DIR)

        # Tests need to clean up explicitly (this is useful since we could skip the
        # cleanup to manually exacmine the temp dir)
        self.addCleanup(self.sb.cleanup)

    ### THE TESTS ###
    def test_basic(self):
        """The sandbox dir has two files
        """
        self.assertEqual(self.sb.lsdir('.'), ['foo1', 'foo2'])

    def test_empty(self):
        """Make a new empty sandbox (ignoring the default)
        """
        sb2 = TestSandbox()
        sb2_dir = sb2.sandbox
        self.assertEqual(sb2.lsdir('.'), [])

        sb2.make('foo777/')
        self.assertTrue(os.path.isdir(sb2_dir + '/foo777'))
        sb2.cleanup()
        self.assertFalse(os.path.isdir(sb2_dir))

    def test_make_touch(self):
        """Do some stuff in the default sandbox
        """
        self.sb.make('d1/d2/d3/afile', days_age=1)
        self.sb.make('da/db/dc/')

        sb_dir = self.sb.sandbox + '/'
        self.assertTrue(os.path.isfile(sb_dir + 'd1/d2/d3/afile'))
        self.assertTrue(os.path.isdir(sb_dir + 'da/db/dc'))

        # Get the current system time
        unixtime = time.time()
        self.assertTrue( os.stat(sb_dir + 'd1/d2/d3/afile').st_mtime < unixtime )

        self.sb.touch('d1/d2')
        self.assertTrue( os.stat(sb_dir + 'd1').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2').st_mtime < unixtime )
        self.assertTrue( os.stat(sb_dir + 'd1/d2/d3').st_mtime < unixtime )
        self.assertTrue( os.stat(sb_dir + 'd1/d2/d3/afile').st_mtime < unixtime )

        self.sb.touch('d1/d2', recursive=True)
        self.assertTrue( os.stat(sb_dir + 'd1').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3/afile').st_mtime < unixtime )

        self.sb.touch('d1/d2/d3/afile', days_age=3)
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3').st_mtime < unixtime )
        self.assertTrue( os.stat(sb_dir + 'd1/d2/d3/afile').st_mtime < unixtime )

        self.sb.touch('.', recursive=True)
        self.assertFalse( os.stat(sb_dir + 'd1').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3/afile').st_mtime < unixtime )

        self.sb.make('d1/d2/d3/bfile', days_age=1)
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3').st_mtime < unixtime )
        self.assertFalse( os.stat(sb_dir + 'd1/d2/d3/afile').st_mtime < unixtime )
        self.assertTrue( os.stat(sb_dir + 'd1/d2/d3/bfile').st_mtime < unixtime )


    def test_errors(self):
        """I can't make a file twice, or touch a file that doesn't exsist.
        """
        self.sb.make("la/la")
        self.assertRaises(FileExistsError, self.sb.make, "la")
        self.assertRaises(FileExistsError, self.sb.make, "la/la")

        # But making a directory that pre-exists is just a no-op
        self.sb.make("la/")

        # I can't touch a file that doesn't exist
        self.assertRaises(FileNotFoundError, self.sb.touch, 'notafile')
        self.assertRaises(FileNotFoundError, self.sb.touch, 'notadir', recursive=True)

        # I can't recursively touch a file
        self.assertRaises(NotADirectoryError, self.sb.touch, 'la/la', recursive=True)

if __name__ == '__main__':
    unittest.main()
