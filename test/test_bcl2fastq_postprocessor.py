#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os, glob, re
from tempfile import mkdtemp
from shutil import rmtree, copytree
from glob import glob

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
#from BCL2FASTQPostprocessor import BCL2FASTQPostprocessor
from BCL2FASTQPostprocessor import main as pp_main
from BCL2FASTQPostprocessor import do_renames, save_projects_ready

class TestBCL2FASTQPreprocessor(unittest.TestCase):

    def setUp(self):
        # Look for test data relative to this Python file
        self.demuxed_dir = os.path.abspath(os.path.dirname(__file__) + '/demuxed_examples')

        self.pp_log = []
        self.pp_proj_list = []

        # See the errors in all their glory
        self.maxDiff = None

    def test_std(self):
        """Modified from the example from the Wiki.  Three files to rename.
           I think we're using the Sample ID and ignoring the Sample Name.
           I've made this explicit.
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.std')

        # Before... just check that the test folder really does have the names I expected.
        in_dir = os.path.join(self.demuxed_dir, '160811_D00261_0355_BC9DA7ANXX.std')
        fqgz_before = glob(in_dir + '/demultiplexing/*/*/*.fastq.gz' )
        fqgz_before = sorted([ f[len(in_dir+'/demultiplexing/'):] for f in fqgz_before ])

        self.assertEqual(fqgz_before, [
            '10510/10510GC0017L01/10510GCpool05_S1_L001_R1_001.fastq.gz',
            '10510/10510GC0017L01/10510GCpool05_S1_L001_R2_001.fastq.gz',
            '10510/10510GC0018L01/10510GCpool05_S2_L001_R1_001.fastq.gz',
            '10510/10510GC0019L01/blahblah_blah_L001_R1_001.fastq.gz',
            ])

        #More self-testing. This sample project has a projects_pending.txt file, right?
        self.assertEqual(slurp(os.path.join(in_dir, 'projects_pending.txt')), ['10510'])

        # And I should still have four .fastq.gz files after processing
        fqgz = glob(out_dir + "/*/*/*.fastq.gz")
        fqgz = sorted([ f[len(out_dir)+1:] for f in fqgz ])

        self.assertEqual(fqgz, [
            '10510/10510GC0017L01/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_1.fastq.gz',
            '10510/10510GC0017L01/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_2.fastq.gz',
            '10510/10510GC0018L01/160811_D00261_0355_BC9DA7ANXX_1_10510GC0018L01_1.fastq.gz',
            '10510/10510GC0019L01/160811_D00261_0355_BC9DA7ANXX_1_10510GC0019L01_1.fastq.gz',
            ])

        #After processing, the projects_ready.txt file should contain the
        #single project number, and projects_pending.txt should be gone.
        self.assertEqual(slurp(os.path.join(out_dir, 'projects_ready.txt')), ['10510'])
        self.assertRaises(FileNotFoundError, slurp, os.path.join(out_dir, 'projects_pending.txt'))

    def test_undetermined(self):
        """Test that undetermined files are renamed correctly. We'll keep the current
           naming scheme of {run}_{lane}_unassigned_{read}.[san]fastq.gz
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.undet')

        fqgz = glob(out_dir + "/*.fastq.gz")
        fqgz = sorted([ f[len(out_dir)+1:] for f in fqgz ])

        self.assertEqual(fqgz, [
            '160811_D00261_0355_BC9DA7ANXX_4_unassigned_1.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_4_unassigned_2.fastq.gz'
            ])

        # projects_ready should be empty as no project files were found
        self.assertEqual(slurp(os.path.join(out_dir, 'projects_ready.txt')), [])

    def test_collision(self):
        """Test that name collisions are trapped as errors, even though this
           should never happen.
        """
        self.assertRaises(FileExistsError,
                          self.run_postprocessor, '160811_D00261_0355_BC9DA7ANXX', '.collision' )

    def test_skip(self):
        """Unrecognised filename pattern should be skipped, but the skip should be logged.
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.skip')

        fqgz = glob(out_dir + "/demultiplexing/*/*/*.fastq.gz")
        fqgz = sorted([ f[len(out_dir+"/demultiplexing/"):] for f in fqgz ])

        # File should still be there
        self.assertEqual(fqgz, [
            '10510/10510GC0017L01/mystery.fastq.gz'
            ])

        # Log should report that it was skipped
        skip_log_lines = [ l for l in self.pp_log if 'skipping' in l ]
        self.assertEqual(len(skip_log_lines), 1)
        self.assertTrue('mystery.fastq.gz' in skip_log_lines[0])

        # projects_ready should be empty as no valid files were found
        self.assertEqual(slurp(os.path.join(out_dir, 'projects_ready.txt')), [])

    # Helper functions
    def run_postprocessor(self, run_id, suffix=''):
        """This will copy a selected test directory into a temp dir, run the postprocessor
           on it and return the path to the temp dir.
           All output will be written to self.pp_log which is jsut a list and can be
           retrieved directly.
           By the magic of cleanup hooks, the temp folder will vanish after the enclosing
           test exits.
        """
        temp_dir = mkdtemp()
        #Add a hook to remove the temp directory at the end of the test, whatever happens.
        self.addCleanup(lambda: rmtree(temp_dir))

        copy_of_test_dir = os.path.join(temp_dir, run_id)
        copytree( os.path.join(self.demuxed_dir, run_id + suffix),
                  copy_of_test_dir,
                  symlinks=True )

        proj_seen = do_renames(copy_of_test_dir, run_id, log=lambda l: self.pp_log.append(l))
        save_projects_ready(copy_of_test_dir, proj_seen)
        self.pp_proj_list.extend(proj_seen)

        return copy_of_test_dir

def slurp(filename):
    with open(filename) as fh:
        return [ l.rstrip('\n') for l in fh ]


if __name__ == '__main__':
    unittest.main()
