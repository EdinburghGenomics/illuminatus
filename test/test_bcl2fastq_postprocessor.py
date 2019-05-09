#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os, glob, re
from tempfile import mkdtemp
from shutil import rmtree, copytree
from glob import glob
from fnmatch import fnmatch

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
#from BCL2FASTQPostprocessor import BCL2FASTQPostprocessor
from BCL2FASTQPostprocessor import main as pp_main
from BCL2FASTQPostprocessor import do_renames, save_projects_ready, ERRORS

VERBOSE = os.environ.get('VERBOSE', '0') != '0'

class T(unittest.TestCase):

    def setUp(self):
        # Look for test data relative to this Python file
        self.demuxed_dir = os.path.abspath(os.path.dirname(__file__) + '/demuxed_examples')

        self.pp_log = []
        self.pp_proj_list = []

        # See the errors in all their glory
        self.maxDiff = None

    def test_std(self):
        """Modified from the example from the Wiki. Also see doc/sample_sheet_pools.txt.
           One standard case where sample name is blank.
           Another where sample name was filled in so we got a subfolder
           And a file that should not be there.
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.std')

        # Before... just check that the test folder really does have the names I expected.
        in_dir = os.path.join(self.demuxed_dir, '160811_D00261_0355_BC9DA7ANXX.std')
        fqgz_before = find_by_pattern(in_dir + '/demultiplexing', '*.fastq.gz' )

        # So the files to be tested are now in the pool__lib format, or are in sub-folders
        # with that format.
        self.assertEqual(fqgz_before, [
            'lane1/10510/10510GCpool05__10510GC0017L01_S1_L001_R1_001.fastq.gz',
            'lane1/10510/10510GCpool05__10510GC0017L01_S999_L001_R2_001.fastq.gz',
            'lane1/10510/10510GCpool05__10510GC0018L01/10510GCpool05_S2_L001_R1_001.fastq.gz',
            'lane1/10510/10510GCpool05__10510GC0018L01/filename_should_be_ignored_S2_L001_R2_001.fastq.gz',
            ])


        #More self-testing. This sample project has a projects_pending.txt file, right?
        self.assertEqual(slurp(os.path.join(in_dir, 'projects_pending.txt')), ['10510'])

        # Now to look at the actual output
        if VERBOSE:
            os.system("tree " + in_dir)
            os.system("tree " + out_dir)

        # All remanes should work
        fqgz_renamed = find_by_pattern(out_dir, "*.fastq.gz")
        self.assertEqual(fqgz_renamed, [
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_1.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_2.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0018L01_1.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0018L01_2.fastq.gz',
            ])

        #After processing, the projects_ready.txt file should contain the
        #single project number, and projects_pending.txt should be gone.
        self.assertEqual(slurp(os.path.join(out_dir, 'projects_ready.txt')), ['10510'])
        self.assertRaises(FileNotFoundError, slurp, os.path.join(out_dir, 'projects_pending.txt'))

        #Also, the empty project dir should have been removed from demultiplexing
        self.assertTrue(os.path.exists(out_dir + '/demultiplexing/lane1'))
        self.assertFalse(os.path.exists(out_dir + '/demultiplexing/lane1/10510'))

    def test_umi(self):
        """For one sample there are reads3 so we treat read 2 as the UMI read.
           In reality if one sample in a lane has read3 then all must have read3.
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.umi')

        # Now to look at the actual output
        if VERBOSE:
            os.system("tree " + os.path.join(self.demuxed_dir, '160811_D00261_0355_BC9DA7ANXX.umi'))
            os.system("tree " + out_dir)

        fqgz_renamed = find_by_pattern(out_dir, "*.fastq.gz")
        self.assertEqual(fqgz_renamed, [
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_1.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_2.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0017L01_UMI.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0018L01_1.fastq.gz',
            '10510/10510GCpool05/160811_D00261_0355_BC9DA7ANXX_1_10510GC0018L01_2.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_1_unassigned_1.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_1_unassigned_2.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_1_unassigned_UMI.fastq.gz',
            ])

    def test_undetermined(self):
        """Test that undetermined files are renamed correctly. We'll keep the current
           naming scheme of {run}_{lane}_unassigned_{read}.[san]fastq.gz
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.undet')

        fqgz = find_by_pattern(out_dir, "*.fastq.gz")

        # Files should now be at the top level and named correctly.
        self.assertEqual(fqgz, [
            '160811_D00261_0355_BC9DA7ANXX_3_unassigned_1.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_3_unassigned_2.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_4_unassigned_1.fastq.gz',
            '160811_D00261_0355_BC9DA7ANXX_4_unassigned_2.fastq.gz'
            ])

        # projects_ready should be empty as no project files were found
        self.assertEqual(slurp(os.path.join(out_dir, 'projects_ready.txt')), [])

    def test_collision(self):
        """Test that name collisions are trapped as errors. They shouldn't be possible.
        """
        self.assertRaises(FileExistsError,
                          self.run_postprocessor, '160811_D00261_0355_BC9DA7ANXX', '.collision' )

        self.assertRaises(FileExistsError,
                          self.run_postprocessor, '160811_D00261_0355_BC9DA7ANXX', '.collision2' )


    def test_skip(self):
        """Unrecognised filename pattern should be skipped, and this should cause an error.
        """
        out_dir = self.run_postprocessor('160811_D00261_0355_BC9DA7ANXX', '.skip')

        fqgz = find_by_pattern(out_dir + "/demultiplexing", "*.fastq.gz")

        # Files should still be there - all fail either the regex match or the
        # lane sanity-check.
        self.assertEqual(fqgz, [
            'lane1/10510/10510GC0017L01/blahblah_blah_L001_R1_001.fastq.gz',
            'lane1/10510/10510GCpool05__10510GC0017L01/mystery.fastq.gz',
            'lane1/10510/blah_S1_L002_R1_001.fastq.gz',
            'lane1/10510/blahblah_blah_L001_R1_001.fastq.gz',
            ])

        # Log should report that everything was skipped
        skip_log_lines = [ l for l in self.pp_log if 'skipping' in l ]
        self.assertEqual(len(skip_log_lines), 4)

        # And the error logged
        self.assertTrue(ERRORS)

        # projects_ready should be empty as no valid files were found
        self.assertEqual(slurp(os.path.join(out_dir, 'projects_ready.txt')), [])

    # Helper functions
    def run_postprocessor(self, run_id, suffix=''):
        """This will copy a selected test directory into a temp dir, run the postprocessor
           on it and return the path to the temp dir.
           All output will be written to self.pp_log which is just a list and can be
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

        if VERBOSE:
            print(*self.pp_log, sep="\n")
            print(repr(ERRORS))
            os.system("tree {}".format(copy_of_test_dir))

        return copy_of_test_dir

def find_by_pattern(root_path, pattern):
    """Python equivalent of find <root_path> -name <pattern> -type f | sed 's/^<root_path>//' | sort
    """
    return sorted( os.path.join(wt[0][len(root_path)+1:], f)
                   for wt in os.walk(root_path)
                   for f in wt[2]
                   if fnmatch(f, pattern) )

def slurp(filename):
    with open(filename) as fh:
        return [ l.rstrip('\n') for l in fh ]


if __name__ == '__main__':
    unittest.main()
