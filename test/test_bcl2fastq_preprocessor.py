#!/usr/bin/env python3
import unittest
import sys, os, glob

# import stuff from ../bin directory
sys.path.insert(0, '../bin')

from BCL2FASTQPreprocessor import BCL2FASTQPreprocessor

class TestBCL2FASTQPreprocessor(unittest.TestCase):

    def setUp(self):
        # Look for test data relative to this file
        self.seqdata_dir = os.path.abspath(os.path.dirname(__file__) + '/../seqdata_examples')


    def test_miseq_1pool(self):
        """Run in 160603_M01270_0196_000000000-AKGDE is a MISEQ run with 1 pool
           and 10-base barcodes.
        """
        self.run_preprocessor('150602_M01270_0108_000000000-ADWKV', [1])

        # This is how it currently looks
        self.assertEquals(self.bcl2fastq_command_string, "-R '/ifs/seqdata/160603_M01270_0196_000000000-AKGDE' -o '/ifs/runqc/160603_M01270_0196_000000000-AKGDE/Unaligned_SampleSheet_in_HiSeq_format_lanes1_readlen301_index10' --sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'   --use-bases-mask Y300n,I10,Y300n  --tiles=s_[1]  --barcode-mismatches 1  --fastq-compression-level 6")

        # This is how it looks, having been split
        self.assertEquals(self.bcl2fastq_command_split, {
                "-R '/ifs/seqdata/160603_M01270_0196_000000000-AKGDE'",
                "-o '/ifs/runqc/160603_M01270_0196_000000000-AKGDE/Unaligned_SampleSheet_in_HiSeq_format_lanes1_readlen301_index10'",
                "--sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'",
                "--use-bases-mask Y300n,I10,Y300n",
                "--tiles=s_[1]",
                "--barcode-mismatches 1",
                "--fastq-compression-level 6",
            })

        # This is how it probably should look

        # FIXME - how do we override "barcode-mismatches"? Needs a design decision. Investigate if it can
        # be added to the SampleSheet, under Settings, to save us worrying about it here at all.

        self.assertEquals(self.bcl2fastq_command_split, {
                "-R '%s/160603_M01270_0196_000000000-AKGDE'" % self.seqdata_dir,
                "-o '%s'" % ??? ,
                "--sample-sheet 'SampleSheet.csv'",
                "--use-bases-mask Y300n,I10,Y300n",
                "--tiles=s_[1]",
                "--barcode-mismatches 1",  # If anything?
                "--fastq-compression-level 6", # Do we still need this?
            })


        def test_miseq_badlane(self):
            """What if I try to demux a non-exitent lane on a MiSEQ?
            """

            self.assertRaises(Exception,
                    self.run_preprocessor('150602_M01270_0108_000000000-ADWKV', [1,5])
                )

        # Helper functions
        def run_preprocessor(run_name, lanes):
            """Invoke the propocessor, capture the command line in bcl2fastq_command_string
               and the split-out version in bcl2fastq_command_split
            """
            blah blah blah

### See stuff in /home/mberinsk/workspace/new_raw_data_pipeline/BaseMaskExtractor/tests/
