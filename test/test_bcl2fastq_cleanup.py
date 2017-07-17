#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os, glob, re
from tempfile import mkdtemp
from shutil import rmtree, copytree
from io import StringIO
from os import remove

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from BCL2FASTQCleanup import main as _c_main

VERBOSE = os.environ.get('VERBOSE', '0') != '0'

class T(unittest.TestCase):

    def setUp(self):
        # Look for test data relative to this Python file
        self.seqdata_dir = os.path.abspath(os.path.dirname(__file__) + '/demuxed_examples')

        #Always make a fresh temporary folder to be working in
        oldcwd = os.getcwd()
        temp_dir = mkdtemp()
        os.chdir(temp_dir)

        def cleanup():
            os.chdir(oldcwd)
            rmtree(temp_dir)

        # See the errors in all their glory
        self.maxDiff = None

    def c_main(self, *a, **k):

        try:
            return _c_main(*a, **k)
        except:
            raise
        finally:
            if VERBOSE:
                print("After running c_main(*{}, **{})".format(a, k))
                os.system("tree")
                os.system("cat {}/cleanup.log".format(a[0]))

    def copy_run(self, run_id):
        copytree( os.path.join(self.seqdata_dir, run_id),
                  run_id,
                  symlinks=True )

    def test_cleanup_1(self):
        """ Run 170329_K00166_0198_BHJ53FBBXX has three projects.
            Let's clean lanes 1 and 8
        """
        run_id = '170329_K00166_0198_BHJ53FBBXX'
        self.copy_run(run_id)

        #Sanity-check
        self.assertTrue(os.path.exists(run_id + '/' + run_id + '_1_unassigned_1.fastq.gz'))
        self.assertTrue(os.path.exists(run_id + '/' + run_id + '_2_unassigned_1.fastq.gz'))
        self.assertTrue(os.path.exists(run_id + '/demultiplexing/lane1/Undetermined_S0_L001_R2_001.fastq.gz'))
        self.assertTrue(os.path.exists(run_id + '/demultiplexing/lane2/Undetermined_S0_L002_R2_001.fastq.gz'))
        self.c_main(run_id, '1', '8')

        with open(run_id + '/projects_pending.txt') as fh:
            projs = sorted([ l.rstrip('\n') for l in fh ])

            self.assertEqual(projs, ['10799', '10809'])

        # Did the right files get cleaned?
        self.assertFalse(os.path.exists(run_id + '/' + run_id + '_1_unassigned_1.fastq.gz'))
        self.assertTrue(os.path.exists(run_id + '/' + run_id + '_2_unassigned_1.fastq.gz'))
        self.assertFalse(os.path.exists(run_id + '/demultiplexing/lane1/Undetermined_S0_L001_R2_001.fastq.gz'))
        self.assertTrue(os.path.exists(run_id + '/demultiplexing/lane2/Undetermined_S0_L002_R2_001.fastq.gz'))

    def test_cleanup_badargs(self):
        """ Run 170329_K00166_0198_BHJ53FBBXX has three projects.
            Let's ask to clean lanes 8 and 9
        """
        run_id = '170329_K00166_0198_BHJ53FBBXX'
        self.copy_run(run_id)

        self.assertRaises(SystemExit, self.c_main, run_id)
        with open(run_id + '/cleanup.log') as lfh:
            self.assertTrue("No lanes specified" in list(lfh)[-1])

        self.assertRaises(SystemExit, self.c_main, run_id, '8', '9')
        with open(run_id + '/cleanup.log') as lfh:
            self.assertTrue("not a valid lane" in list(lfh)[-1])

        # With non-existent run
        self.assertRaises(FileNotFoundError, self.c_main, "nosuchrun", '4', '5')
