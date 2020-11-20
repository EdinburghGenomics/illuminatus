#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os, re
from glob import glob
from tempfile import mkdtemp
from shutil import rmtree, copytree
from io import StringIO
from os import remove

# Adding this to sys.path makes the test work if you just run it directly.
with patch('sys.path', new=['.'] + sys.path):
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

        if os.environ.get("KEEPTMP"):
            print(temp_dir, file=sys.stderr)
        else:
            self.addCleanup(cleanup)

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

    def test_cleanup_2(self):
        """180118_K00166_0327_BHNJHGBBXX represent a fully processed run
           with 2 projects. I've cut it down to 3 lanes.
        """
        run_id = '180118_K00166_0327_BHNJHGBBXX'
        self.copy_run(run_id)

        # Sanity-check
        self.assertEqual( len(glob(run_id + '/*_unassigned_*')), 6 )
        self.assertEqual( len(glob(run_id + '/11130/*/*')), 52 )
        self.assertEqual( len(glob(run_id + '/11131/*/*')), 100 )
        self.assertEqual( len(glob(run_id + '/md5sums/*/*/*')), 152 )
        self.assertEqual( len(glob(run_id + '/counts/*/*/*')), 152 )
        self.assertEqual( len(glob(run_id + '/QC/lane*')), 3 )
        self.assertEqual( len(glob(run_id + '/demultiplexing/lane*')), 3 )
        with open(run_id + '/projects_ready.txt') as fh:
            self.assertEqual(sorted([ l.rstrip('\n') for l in fh ]), ['11130', '11131'])

        # Clean lane 1 should leave project 11131 pending
        self.c_main(run_id, '1')
        with open(run_id + '/projects_pending.txt') as fh:
            self.assertEqual(sorted([ l.rstrip('\n') for l in fh ]), ['11131'])

        # But projects_ready.txt stays as it is (I think?)
        with open(run_id + '/projects_ready.txt') as fh:
            self.assertEqual(sorted([ l.rstrip('\n') for l in fh ]), ['11130', '11131'])

        # And we should have removed the appropriate number of everything
        self.assertEqual( len(glob(run_id + '/*_unassigned_*')), 4 )
        self.assertEqual( len(glob(run_id + '/11130/*/*')), 52 )
        self.assertEqual( len(glob(run_id + '/11131/*/*')), 50 )
        self.assertEqual( len(glob(run_id + '/md5sums/*/*/*')), 102 )
        self.assertEqual( len(glob(run_id + '/counts/*/*/*')), 102 )
        self.assertEqual( len(glob(run_id + '/QC/lane*')), 2 )
        self.assertEqual( len(glob(run_id + '/demultiplexing/lane*')), 2 )

    def test_cleanup_badname(self):
        """200214_M01270_0118_000000000-CYMPG is a run that didn't clean properly due to
           a funny project name.
        """
        run_id = '200214_M01270_0118_000000000-CYMPG'
        self.copy_run(run_id)

        # Check the test data is as expected
        with open(run_id + '/projects_ready.txt') as fh:
            self.assertEqual(sorted([ l.rstrip('\n') for l in fh ]), ['12000', '1200C'])

        # Clean lane 1 should leave both pending (and projects_ready untouched)
        self.c_main(run_id, '1')

        with open(run_id + '/projects_ready.txt') as fh:
            self.assertEqual(sorted([ l.rstrip('\n') for l in fh ]), ['12000', '1200C'])
        with open(run_id + '/projects_pending.txt') as fh:
            self.assertEqual(sorted([ l.rstrip('\n') for l in fh ]), ['12000', '1200C'])

        # And we should have removed absolutely everything
        self.assertEqual( len(glob(run_id + '/*_unassigned_*')), 0 )
        self.assertEqual( len(glob(run_id + '/12*')), 0 )
        self.assertEqual( len(glob(run_id + '/md5sums/*')), 0 )
        self.assertEqual( len(glob(run_id + '/counts/*')), 0 )
        self.assertEqual( len(glob(run_id + '/QC/lane*')), 0 )
        self.assertEqual( len(glob(run_id + '/demultiplexing/lane*')), 0 )

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
