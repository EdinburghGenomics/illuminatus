#!/usr/bin/env python3

"""bcl2fastq_setup.py makes the per-lane sample sheet fragment actually used
   to run bcl2fastq.
"""

import sys, os, re
import unittest
import logging
from pprint import pprint

from tempfile import mkdtemp
from shutil import rmtree, copytree
from configparser import DuplicateOptionError

DATA_DIR = os.path.join( os.path.abspath(os.path.dirname(__file__)),
                         'seqdata_examples' )
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from bcl2fastq_setup import BCL2FASTQPreprocessor, revcomp

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
        run_dir = os.path.join(DATA_DIR, run_name)

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
        pp = BCL2FASTQPreprocessor( run_source_dir = self.get_ex(run_id),
                                    lane = "1",
                                    revcomp = None )

        self.assertCountEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                             "--use-bases-mask 'Y300n,I10,Y300n'",
                                                             "--tiles 's_[1]'",
                                                             "--barcode-mismatches 1" ] )
        self.assertEqual( pp.infer_revcomp(), '' )

        out_lines = pp.get_output('test')

        self.assertEqual( [ l for l in out_lines if l.startswith('[') ],
                          [ '[Header]', '[bcl2fastq]', '[Data]' ] )

    def test_miseq_1pool_c(self):
        """Same as above but with the -c/--bc_check flag
        """
        run_id = '160603_M01270_0196_000000000-AKGDE'
        pp = BCL2FASTQPreprocessor( run_source_dir = self.get_ex(run_id),
                                    lane = "1",
                                    revcomp = None,
                                    bc_check = True )

        self.assertCountEqual( pp.get_bc_check_opts(), [ "--fastq-compression-level 6",
                                                         "--use-bases-mask 'Yn*,I10,n*'",
                                                         "--tiles 's_[1]_1101'",
                                                         "--barcode-mismatches 1",
                                                         "--interop-dir .",
                                                         "--minimum-trimmed-read-length 1" ] )

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
            print("--tiles: 's_[1]_1101'", file=f)

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "1",
                                    revcomp = None )

        self.assertCountEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                             "--use-bases-mask 'Y50n,I8,I8'",
                                                             "--tiles 's_[1]_1101'",
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

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "2",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ '--fastq-compression-level 6',
                                                             "--use-bases-mask 'Y50n,I8,I8'",
                                                             "--tiles 's_[2]'",
                                                             '--foo bar',
                                                             '--barcode-mismatches 2' ] )

        # Now add pipeline_settings.ini
        with open(ini_file, "w") as fh:
            print("[bcl2fastq]", file=fh)
            print("--barcode-mismatches: 9", file=fh)
            print("--barcode-mismatches-lane8: 8", file=fh)

        # This is now 9 - .ini file takes precedence
        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "2",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ '--fastq-compression-level 6',
                                                             "--use-bases-mask 'Y50n,I8,I8'",
                                                             "--tiles 's_[2]'",
                                                             '--foo bar',
                                                             '--barcode-mismatches 9' ] )

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "8",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ '--fastq-compression-level 6',
                                                             "--use-bases-mask 'Y50n,I8,n*'",
                                                             "--tiles 's_[8]'",
                                                             '--foo bar',
                                                             '--barcode-mismatches 8' ] )

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "1",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ '--fastq-compression-level 6',
                                                             "--use-bases-mask 'Y50n,I8,I8'",
                                                             "--tiles 's_[1]'",
                                                             '--foo bar',
                                                             '--barcode-mismatches 9' ] )

    def test_basemask_override(self):
        """Setting basemask per lane should work. We could make it a pseudo option
           like --barcode-mismatches-laneN or we could use the : syntax which is already
           in bcl2fastq. Heck, support both.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.get_ex(run_id, shadow=True)

        ini_file = os.path.join(shadow_dir, "pipeline_settings.ini")
        self.assertFalse(os.path.exists( ini_file ))

        with open(os.path.join(shadow_dir, 'SampleSheet.csv'), "r") as fh:
            lines = list(fh)

        # Munge the SampleSheet.csv with extra headings
        with open(os.path.join(shadow_dir, 'SampleSheet.csv'), "w") as fh:
            print("[bcl2fastq]\n", file=fh)
            print("--use-bases-mask-lane1: 1:Y147,I8Y11,I8,Y147", file=fh)
            print("--use-bases-mask-lane2: Y147,I8n*,I8,Y147", file=fh)
            print("--use-bases-mask: 'default'", file=fh)
            print("", file=fh)
            for l in lines: print(l, file=fh, end='')

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "1",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask 1:Y147,I8Y11,I8,Y147",
                                                        "--tiles 's_[1]'" ] )

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "2",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options()[1], "--use-bases-mask Y147,I8n*,I8,Y147" )

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "3",
                                    revcomp = None )
        self.assertEqual( pp.get_bcl2fastq_options()[1], "--use-bases-mask 'default'"  )

        # Other syntax doesn't work. This isn't so much a test as a demonstration of why
        # it breaks.
        with open(os.path.join(shadow_dir, 'SampleSheet.csv'), "w") as fh:
            print("[bcl2fastq]\n", file=fh)
            print("--use-bases-mask: 1:Y147,I8Y11,I8,Y147", file=fh)
            print("--use-bases-mask: 2:Y147,I8n*,I8,Y147", file=fh)
            print("--use-bases-mask: wrong", file=fh)
            print("", file=fh)
            for l in lines: print(l, file=fh, end='')

        with self.assertRaises(DuplicateOptionError):
            # This won't work without totally changing the option parsing logic!
            pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                        lane = "2",
                                        revcomp = None )

    def test_slimmed_run(self):
        """Check a setup produced by slim_a_novaseq_run.sh
        """
        run_id = "220113_A00291_0410_AHV23HDRXY"
        pp = BCL2FASTQPreprocessor( run_source_dir = self.get_ex(run_id),
                                    lane = "1",
                                    revcomp = None )

        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask 'Y150n,I8,I8,Y150n'",
                                                        "--tiles 's_[1]_2101'" ] )


    def test_slimmed_run_c(self):
        """Check a setup produced by slim_a_novaseq_run.sh, with the --bc_check flag
        """
        run_id = "220113_A00291_0410_AHV23HDRXY"
        pp = BCL2FASTQPreprocessor( run_source_dir = self.get_ex(run_id),
                                    lane = "1",
                                    revcomp = None,
                                    bc_check = True )

        self.assertEqual( pp.get_bc_check_opts(), [ "--fastq-compression-level 6",
                                                    "--use-bases-mask 'Yn*,I8,I8,n*'",
                                                    "--tiles 's_[1]_2101'",
                                                    "--interop-dir .",
                                                    "--minimum-trimmed-read-length 1" ] )

    def test_nocolon_override(self):
        """SampleSheet.csv should be allowed to override barcode-mismatches etc.
           To be compatible with the processed format this needs to work with no colon.
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
            print("--foo bar", file=fh)
            print("--barcode-mismatches 2", file=fh)
            print("--barcode-mismatches-lane4 4", file=fh)
            print("", file=fh)
            for l in lines: print(l, file=fh, end='')

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "2",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                             "--use-bases-mask 'Y50n,I8,I8'",
                                                             "--tiles 's_[2]'",
                                                             "--foo bar",
                                                             "--barcode-mismatches 2" ] )

        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "4",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                             "--use-bases-mask 'Y50n,I8,n*'",
                                                             "--tiles 's_[4]'",
                                                             "--foo bar",
                                                             "--barcode-mismatches 4" ] )

    def test_miseq_badlane(self):
        """What if I try to demux a non-existent lane on a MiSEQ?
        """
        self.assertRaises( AssertionError,
                BCL2FASTQPreprocessor, run_source_dir = self.get_ex('150602_M01270_0108_000000000-ADWKV'),
                                       lane = '5',
                                       revcomp = None )

    def test_hiseq_lanes_5_retry(self):
        """ This has all sorts of stuff. Lane 5 has no index.
            The --barcode-mismatch will not be set so we need to try both options.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        pp = BCL2FASTQPreprocessor( run_source_dir = self.get_ex(run_id),
                                    lane = "5",
                                    revcomp = None )

        self.assertEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                        "--use-bases-mask 'Y50n,n*,n*'",
                                                        "--tiles 's_[5]'" ] )

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
        pp = BCL2FASTQPreprocessor( run_source_dir = shadow_dir,
                                    lane = "5",
                                    revcomp = None )
        self.assertCountEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                             "--use-bases-mask 'Y50n,n*,n*'",
                                                             "--tiles 's_[5]'",
                                                             "--barcode-mismatches 1" ] )

        #Lane 1 has 8-base dual index
        pp = BCL2FASTQPreprocessor(shadow_dir, lane=1, revcomp=None)
        self.assertEqual(pp.get_bcl2fastq_options()[1], "--use-bases-mask 'Y50n,I8,I8'")

        #Lane 3 has 6-base single index
        pp = BCL2FASTQPreprocessor(shadow_dir, lane=3, revcomp=None)
        self.assertEqual(pp.get_bcl2fastq_options()[1], "--use-bases-mask 'Y50n,I6n*,n*'")

        #Lane 4 has 8-base single index
        pp = BCL2FASTQPreprocessor(shadow_dir, lane=4, revcomp=None)
        self.assertEqual(pp.get_bcl2fastq_options()[1], "--use-bases-mask 'Y50n,I8,n*'")

    def test_auto_revcomp(self):
        """ Run 201125_A00291_0321_AHWHKYDRXX is the original one that needed a revcomp
        """
        run_id = '201125_A00291_0321_AHWHKYDRXX'
        run_dir = self.get_ex(run_id, shadow=False)

        out_lines = BCL2FASTQPreprocessor( run_source_dir = run_dir,
                                           lane = "1",
                                           revcomp = None ).get_output('test')
        self.assertEqual( out_lines[-4], '[Data]' )
        self.assertEqual( out_lines[-3].split(',')[0], 'Lane' )
        self.assertEqual( out_lines[-3].split(',')[7], 'index' )
        self.assertEqual( out_lines[-3].split(',')[9], 'index2' )

        # With no revcomp, we get this...
        self.assertEqual( out_lines[-1].split(',')[0], '1' )
        self.assertEqual( out_lines[-1].split(',')[7], 'TTATAACC' )
        self.assertEqual( out_lines[-1].split(',')[9], 'GATATCGA' )

        # With forced double revcomp, this
        out_lines = BCL2FASTQPreprocessor( run_source_dir = run_dir,
                                           lane = "1",
                                           revcomp = "12" ).get_output('test')
        self.assertEqual( out_lines[-1].split(',')[7], 'GGTTATAA' )
        self.assertEqual( out_lines[-1].split(',')[9], 'TCGATATC' )

        # Auto revcomp just modifies the second index
        pp = BCL2FASTQPreprocessor( run_source_dir = run_dir,
                                    lane = "1",
                                    revcomp = "auto" )
        out_lines = pp.get_output('test')

        self.assertEqual( pp.infer_revcomp(), '2' )
        self.assertEqual( out_lines[-1].split(',')[7], 'TTATAACC' )
        self.assertEqual( out_lines[-1].split(',')[9], 'TCGATATC' )

    def test_empty_samplesheet(self):
        """If there is no sample sheet the pipeline generates an empty file.
           We want a clean error.
        """
        run_id = '160606_K00166_0102_BHF22YBBXX'
        run_dir = self.get_ex(run_id, shadow=False)

        self.assertRaises( AssertionError,
                BCL2FASTQPreprocessor, run_source_dir = run_dir,
                                       lane = "1",
                                       revcomp = None )

    def test_with_settings(self):
        """To support the built-in UMI processing functionality of bcl2fastq we
           need to allow for a [Settings] section to exist in the sample sheet
           and for the default basemask to be suppressed if the settings
           section is present.
        """
        for run_id in [ '230602_A00291_0400_BHKT2KDMAA',
                        '230602_A00291_0400_BHKT2KDMBB' ]:
            run_dir = self.get_ex(run_id, shadow=False)

            pp = BCL2FASTQPreprocessor( run_source_dir = run_dir,
                                        lane = "1",
                                        revcomp = 'auto' )
            out_lines = pp.get_output(created_by='test')

            # Check we have the expected options, with no base mask
            self.assertCountEqual( pp.get_bcl2fastq_options(), [ "--fastq-compression-level 6",
                                                                 "--tiles 's_[1]'" ] )

            # Check we have the [settings] as expected
            self.assertCountEqual( [ l for l in out_lines if l.startswith('[') ],
                                   [ '[Header]', '[bcl2fastq]', '[Settings]', '[Data]' ] )

            # Check we have 8 lines beginning with 'Read' then a blank line
            s_pos = out_lines.index('[Settings]')
            self.assertEqual( [ l[:4] for l in out_lines[s_pos+1:s_pos+10] ],
                              (['Read'] * 8) + [''] )

if __name__ == '__main__':
    unittest.main()
