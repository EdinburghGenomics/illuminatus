#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import subprocess
import sys, os, glob, re
from tempfile import mkdtemp
from shutil import rmtree, copytree
from io import StringIO
from os import remove

# Adding this to sys.path makes the test work if you just run it directly.
with patch('sys.path', new=['.'] + sys.path):
    from BCL2FASTQPreprocessor import BCL2FASTQPreprocessor
    from BCL2FASTQPreprocessor import main as pp_main

class T(unittest.TestCase):

    def setUp(self):
        # Look for test data relative to this Python file
        self.seqdata_dir = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')

        # If the proprocessor actually needs to write anything then I'll need
        # to replace this with tmpdir and to clean it up afterwards.
        self.out_dir = '/mock/out'

        # See the errors in all their glory
        self.maxDiff = None

        self.tmp_dir = None
        self.shadow_runs = dict()

    # TODO - use binmocker to test the actual script that is produced.

    def test_miseq_1pool(self):
        """Run in 160603_M01270_0196_000000000-AKGDE is a MISEQ run with 1 pool
           and 10-base barcodes.
           --barcode-mismatches is set to 1
        """
        run_id = '160603_M01270_0196_000000000-AKGDE'
        self.run_preprocessor(run_id, 1)

        self.assertEqual(self.template_args, dict(
                                    lane = "1",
                                    bcl2fastq = self.bcl2fastq_path,
                                    samplesheet = os.path.join(self.run_dir, "SampleSheet.csv"),
                                    barcode_mismatches = "1",
                                    destdir = self.out_dir,
                                    rundir = self.run_dir,
                                    runid = run_id,
                                    bcl2fastq_opts = [ "--fastq-compression-level 6",
                                                       "--use-bases-mask '1:Y300n,I10,Y300n'",
                                                       "--tiles=s_[$LANE]",
                                                       "--barcode-mismatches 1" ] ))

    def test_settings_file(self):
        """settings file test: should override the defaults
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.shadow_run(run_id)
        ini_file = os.path.join(shadow_dir, "pipeline_settings.ini")

        # Check setting some overrides in the .ini file. {lanes} should be substituted for the
        # list of lanes.
        with open( ini_file , 'w') as f:
            print("[bcl2fastq]", file=f)
            print("--barcode-mismatches: 100", file=f)
            print("--tiles: s_[$LANE]_1101", file=f)

        self.run_preprocessor(run_id, 1)

        self.assertEqual(self.template_args, dict(
                                    lane = "1",
                                    bcl2fastq = self.bcl2fastq_path,
                                    samplesheet = os.path.join(self.run_dir, "SampleSheet.csv"),
                                    barcode_mismatches = "100",
                                    destdir = self.out_dir,
                                    rundir = self.run_dir,
                                    runid = run_id,
                                    bcl2fastq_opts = [ "--fastq-compression-level 6",
                                                       "--use-bases-mask '1:Y50n,I8,I8'",
                                                       "--tiles=s_[$LANE]_1101",
                                                       "--barcode-mismatches 100", ] ))

    def test_settings_override(self):
        """SampleSheet.csv should be allowed to override barcode-mismatches.
           If the pipeline_settings.ini overrides the barcode-mismatches setting then it should
           apply to all lanes.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.shadow_run(run_id)

        self.assertFalse(os.path.exists(
            os.path.join(shadow_dir, 'pipeline_settings.ini') ))

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

        # This time, just test up to initialization
        bfp = BCL2FASTQPreprocessor(shadow_dir, 2)

        self.assertEqual(dict(bfp.ini_settings),
                         dict( bcl2fastq = {
                            '--foo': 'bar',
                            '--barcode-mismatches': '2'} ))

        # Now add pipeline_settings.ini
        with open(os.path.join(shadow_dir, 'pipeline_settings.ini'), "w") as fh:
            print("[bcl2fastq]", file=fh)
            print("--barcode-mismatches: 9", file=fh)
            print("--barcode-mismatches-lane8: 8", file=fh)

        bfp = BCL2FASTQPreprocessor(shadow_dir, 8)
        self.assertEqual(dict(bfp.ini_settings),
                         dict( bcl2fastq = {
                            '--foo': 'bar',
                            '--barcode-mismatches': '8'} ))

        bfp = BCL2FASTQPreprocessor(shadow_dir, 1)
        self.assertEqual(dict(bfp.ini_settings),
                         dict( bcl2fastq = {
                            '--foo': 'bar',
                            '--barcode-mismatches': '9'} ))

    def test_miseq_badlane(self):
        """What if I try to demux a non-existent lane on a MiSEQ?
        """
        self.assertRaises(AssertionError,
                self.run_preprocessor, '150602_M01270_0108_000000000-ADWKV', '5'
            )

    def test_hiseq_lanes_5_retry(self):
        """ This has all sorts of stuff. Lane 5 has no index.
            The --barcode-mismatch will not be set so we need to try both options.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        #Run on lane 5
        self.run_preprocessor(run_id, 5)

        self.assertEqual(self.template_args, dict(
                                    lane = "5",
                                    bcl2fastq = self.bcl2fastq_path,
                                    samplesheet = os.path.join(self.run_dir, "SampleSheet.csv"),
                                    barcode_mismatches = None,
                                    destdir = self.out_dir,
                                    rundir = self.run_dir,
                                    runid = run_id,
                                    bcl2fastq_opts = [ "--fastq-compression-level 6",
                                                       "--use-bases-mask '5:Y50n,n*,n*'",
                                                       "--tiles=s_[$LANE]" ] ))

    def test_hiseq_lanes_5_simple(self):
        """ This has all sorts of stuff. Lane 5 has no index.
            The --barcode-mismatch will be explicitly set to 1.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        shadow_dir = self.shadow_run(run_id)

        ini_file = os.path.join(shadow_dir, "pipeline_settings.ini")
        with open( ini_file , 'w') as f:
            print("[bcl2fastq]", file=f)
            print("--barcode-mismatches: 1", file=f)

        #Run on lane 5
        self.run_preprocessor(run_id, 5)

        self.assertEqual(self.template_args, dict(
                                    lane = "5",
                                    bcl2fastq = self.bcl2fastq_path,
                                    samplesheet = os.path.join(self.run_dir, "SampleSheet.csv"),
                                    barcode_mismatches = "1",
                                    destdir = self.out_dir,
                                    rundir = self.run_dir,
                                    runid = run_id,
                                    bcl2fastq_opts = [ "--fastq-compression-level 6",
                                                       "--use-bases-mask '5:Y50n,n*,n*'",
                                                       "--tiles=s_[$LANE]",
                                                       "--barcode-mismatches 1" ] ))

        #Lane 1 has 8-base dual index
        self.run_preprocessor(run_id, 1)
        self.assertEqual(self.template_args['bcl2fastq_opts'][1], "--use-bases-mask '1:Y50n,I8,I8'")

        #Lane 3 has 6-base single index
        self.run_preprocessor(run_id, 3)
        self.assertEqual(self.template_args['bcl2fastq_opts'][1], "--use-bases-mask '3:Y50n,I6n*,n*'")

        #Lane 4 has 8-base single index
        self.run_preprocessor(run_id, 4)
        self.assertEqual(self.template_args['bcl2fastq_opts'][1], "--use-bases-mask '4:Y50n,I8,n*'")


    @patch('sys.stdout', new_callable=StringIO)
    @patch('BCL2FASTQPreprocessor.check_output', side_effect=['bcl2fastq'])
    def test_main(self, mock_check_output, mock_stdout):
        """Test the main function. This is another one that writes a file
           so make a temp dir for the file to go into.
           Use run 160607_D00248_0174_AC9E4KANXX for this test.
        """
        #Make the temp dir
        out_dir = mkdtemp()
        #Add a hook to remove the temp directory even if the test fails
        self.addCleanup(lambda: rmtree(out_dir))

        data_dir = os.path.join(self.seqdata_dir, '160607_D00248_0174_AC9E4KANXX')

        #Now we can run main(run_dir, dest) on, say, lane 8.
        pp_main(data_dir, out_dir, 8)

        # Open the script that was just outputted.
        script = os.path.join(out_dir, 'do_demultiplex8.sh')
        self.assertTrue(os.path.exists(script))
        #self.assertTrue(os.access(script, os.X_OK))
        with open(script) as fh:
            script_lines = [l.rstrip() for l in list(fh)]

        self.assertEqual(script_lines[0], '#!/bin/bash')

        #The preprocessor should also output the script plus a preamble
        stdout_lines = [ l for l in
                         mock_stdout.getvalue().strip('\n').split('\n')
                         if ( not 'END' in l and not '>>>' in l) ]

        self.assertEqual(stdout_lines, script_lines)

    # Helper functions
    def shadow_run(self, run_name):
        """Copy a run so I can write to it.
        """
        run_dir = os.path.join(self.seqdata_dir, run_name)

        if not self.tmp_dir:
            self.tmp_dir = mkdtemp()
            self.addCleanup(lambda: rmtree(self.tmp_dir))

        self.shadow_runs[run_name] = os.path.join(self.tmp_dir, 'seqdata', run_name)

        return copytree( run_dir,
                         os.path.join(self.tmp_dir, 'seqdata', run_name),
                         symlinks = True )


    @patch('BCL2FASTQPreprocessor.check_output', side_effect=['dummy_bcl2fastq'])
    def run_preprocessor(self, run_name, lane, mock_check_output):
        """Invoke the preprocessor, capturing the output in self.template_args
           This will be a dict suitable for use in the template.
        """
        if run_name in self.shadow_runs:
            self.run_dir = self.shadow_runs[run_name]
        else:
            self.run_dir = os.path.join(self.seqdata_dir, run_name)

        self.pp = BCL2FASTQPreprocessor( run_dir = self.run_dir,
                                         lane = lane,
                                         dest = self.out_dir )

        self.template_args = self.pp.get_bcl2fastq_commands()

        # Given the override of check_output, I expect bcl2fastq to be 'found'
        # in the cwd
        self.bcl2fastq_path = os.path.realpath('dummy_bcl2fastq')



### See stuff in /home/mberinsk/workspace/new_raw_data_pipeline/BaseMaskExtractor/tests/

if __name__ == '__main__':
    unittest.main()
