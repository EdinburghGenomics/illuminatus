#!/usr/bin/env python3

"""bcl2fastq_setup.py makes the per-lane sample sheet fragment actually used
   to run bcl2fastq.
"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
from unittest.mock import patch
import logging
from pprint import pprint

from tempfile import mkdtemp
from shutil import rmtree, copytree

DATA_DIR = os.path.abspath(os.path.dirname(__file__))
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

try:
    # This is a safe way to manipulate sys.path without impacting later tests.
    with patch('sys.path', new=['.'] + sys.path):
        from bcl2fastq_setup import BCL2FASTQPreprocessor, revcomp
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

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None
        self.tmp_dir = None

    def tearDown(self):
        pass

    def get_ex(self, run_name, shadow=False):
        """Get an example run from the examples dir
        """
        run_dir = os.path.join(DATA_DIR, 'seqdata_examples', run_name)

        if shadow:
            # OK we want a temporary copy of the run dir to modify
            if not self.tmp_dir:
                self.tmp_dir = mkdtemp()
                self.addCleanup(lambda: rmtree(self.tmp_dir))

            run_shadow = os.path.join(self.tmp_dir, 'seqdata', run_name)

            copytree( run_dir, run_shadow, symlinks=True )
            return run_shadow

        else:
            # Read-only so no need for a copy
            return run_dir

    ### THE TESTS ###
    def test_revcomp(self):
        """A basic reverse complement function
        """

        self.assertEqual(revcomp(''), '')
        self.assertEqual(revcomp('ATCG'), 'CGAT')
        self.assertEqual(revcomp('AAANNNTTT'), 'AAANNNTTT')

    # Tests adapted from test_bcl2fastq_preprocessor.py
    def test_miseq_1pool(self):
        """Run in 160603_M01270_0196_000000000-AKGDE is a MISEQ run with 1 pool
           and 10-base barcodes.
           --barcode-mismatches is set to 1
        """
        run_id = '160603_M01270_0196_000000000-AKGDE'
        pp = BCL2FASTQPreprocessor( run_dir = self.get_ex(run_id),
                                    lane = "1",
                                    revcomp = None )

        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask '1:Y300n,I10,Y300n'",
                                                        "--tiles=s_[$LANE]",
                                                        "--barcode-mismatches 1" ] )
        self.assertEqual( pp.infer_revcomp(), '' )

        out_lines = pp.get_output('test')

        self.assertEqual( [ l for l in out_lines if l.startswith('[') ],
                          [ '[Header]', '[bcl2fastq]', '[Data]' ] )


    def test_settings_file(self):
        """settings file test: should override the defaults
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.get_ex(run_id, shadow=True)
        ini_file = os.path.join(shadow_dir, "pipeline_settings.ini")

        # Check setting some overrides in the .ini file.
        with open( ini_file , 'w') as f:
            print("[bcl2fastq]", file=f)
            print("--barcode-mismatches: 100", file=f)
            print("--tiles: s_[$LANE]_1101", file=f)

        pp = BCL2FASTQPreprocessor( run_dir = shadow_dir,
                                    lane = "1",
                                    revcomp = None )

        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask '1:Y50n,I8,I8'",
                                                        "--tiles=s_[$LANE]_1101",
                                                        "--barcode-mismatches 100" ] )


    def test_settings_override(self):
        """SampleSheet.csv should be allowed to override barcode-mismatches.
           If the pipeline_settings.ini overrides the barcode-mismatches setting then it should
           apply to all lanes.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.get_ex(run_id, shadow=True)

        ini_file = os.path.join(shadow_dir, "pipeline_settings.ini")
        self.assertFalse(os.path.exists( ini_file ))

        # Munge the SampleSheet.csv with an extra heading.
        with open(os.path.join(shadow_dir, 'SampleSheet.csv'), "r") as fh:
            lines = list(fh)
        with open(os.path.join(shadow_dir, 'SampleSheet.csv'), "w") as fh:
            print("[bcl2fastq]", file=fh)
            print("", file=fh)
            print("--foo: bar", file=fh)
            print("--barcode-mismatches-lane2: 2", file=fh)
            print("--barcode-mismatches-lane4: 4", file=fh)
            print("", file=fh)
            for l in lines: print(l, file=fh, end='')

        pp = BCL2FASTQPreprocessor( run_dir = shadow_dir,
                                    lane = "2",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options()[-2:], [ '--foo bar',
                                                             '--barcode-mismatches 2' ] )

        # Now add pipeline_settings.ini
        with open(ini_file, "w") as fh:
            print("[bcl2fastq]", file=fh)
            print("--barcode-mismatches: 9", file=fh)
            print("--barcode-mismatches-lane8: 8", file=fh)

        # This is now 9 - .ini file takes precedence
        pp = BCL2FASTQPreprocessor( run_dir = shadow_dir,
                                    lane = "2",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options()[-2:], [ '--foo bar',
                                                             '--barcode-mismatches 9' ] )

        pp = BCL2FASTQPreprocessor( run_dir = shadow_dir,
                                    lane = "8",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options()[-2:], [ '--foo bar',
                                                             '--barcode-mismatches 8' ] )

        pp = BCL2FASTQPreprocessor( run_dir = shadow_dir,
                                    lane = "1",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options()[-2:], [ '--foo bar',
                                                             '--barcode-mismatches 9' ] )

    def test_miseq_badlane(self):
        """What if I try to demux a non-existent lane on a MiSEQ?
        """
        self.assertRaises( AssertionError,
                BCL2FASTQPreprocessor, run_dir = self.get_ex('150602_M01270_0108_000000000-ADWKV'),
                                       lane = '5',
                                       revcomp = None )

    def test_hiseq_lanes_5_retry(self):
        """ This has all sorts of stuff. Lane 5 has no index.
            The --barcode-mismatch will not be set so we need to try both options.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        pp = BCL2FASTQPreprocessor( run_dir = self.get_ex(run_id),
                                    lane = "5",
                                    revcomp = None )

        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask '5:Y50n,n*,n*'",
                                                        "--tiles=s_[$LANE]" ] )

    def test_hiseq_lanes_5_simple(self):
        """ This has all sorts of stuff. Lane 5 has no index.
            The --barcode-mismatch will be explicitly set to 1.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.get_ex(run_id, shadow=True)

        ini_file = os.path.join(shadow_dir, "pipeline_settings.ini")
        with open( ini_file , 'w') as f:
            print("[bcl2fastq]", file=f)
            print("--barcode-mismatches: 1", file=f)

        #Run on lane 5
        pp = BCL2FASTQPreprocessor( run_dir = shadow_dir,
                                    lane = "5",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask '5:Y50n,n*,n*'",
                                                        "--tiles=s_[$LANE]",
                                                        "--barcode-mismatches 1" ] )

        #Lane 1 has 8-base dual index
        pp = BCL2FASTQPreprocessor(shadow_dir, "1", None)
        self.assertEqual(pp.get_bcl2fastq_options()[1], "--use-bases-mask '1:Y50n,I8,I8'")

        #Lane 3 has 6-base single index
        pp = BCL2FASTQPreprocessor(shadow_dir, "3", None)
        self.assertEqual(pp.get_bcl2fastq_options()[1], "--use-bases-mask '3:Y50n,I6n*,n*'")

        #Lane 4 has 8-base single index
        pp = BCL2FASTQPreprocessor(shadow_dir, "4", None)
        self.assertEqual(pp.get_bcl2fastq_options()[1], "--use-bases-mask '4:Y50n,I8,n*'")


if __name__ == '__main__':
    unittest.main()
