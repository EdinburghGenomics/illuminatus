#!/usr/bin/env python3
import unittest
import sys, os, glob, re

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from BCL2FASTQPreprocessor import BCL2FASTQPreprocessor

class TestBCL2FASTQPreprocessor(unittest.TestCase):

    def setUp(self):
        # Look for test data relative to this Python file
        self.seqdata_dir = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')

        # If the proprocessor actually needs to write anything then I'll need
        # to replace this with tmpdir and to clean it up afterwards.
        self.out_dir = '/mock/out'

        # See the errors in all their glory
        self.maxDiff = None

    def test_miseq_1pool(self):
        """Run in 160603_M01270_0196_000000000-AKGDE is a MISEQ run with 1 pool
           and 10-base barcodes.
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'
        self.run_preprocessor(run_id, [1])

        # This is how it currently looks
        #self.assertEqual(self.bcl2fastq_command_string, "-R '/ifs/seqdata/160603_M01270_0196_000000000-AKGDE' -o '/ifs/runqc/160603_M01270_0196_000000000-AKGDE/Unaligned_SampleSheet_in_HiSeq_format_lanes1_readlen301_index10' --sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'   --use-bases-mask Y300n,I10,Y300n  --tiles=s_[1]  --barcode-mismatches 1  --fastq-compression-level 6")

        # This is how it looks, having been split
        '''
        self.assertEqual(self.bcl2fastq_command_split, [
                "-R '/ifs/seqdata/160603_M01270_0196_000000000-AKGDE'",
                "-o '/ifs/runqc/160603_M01270_0196_000000000-AKGDE/Unaligned_SampleSheet_in_HiSeq_format_lanes1_readlen301_index10'",
                "--sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'",
                "--use-bases-mask Y300n,I10,Y300n",
                "--tiles=s_[1]",
                "--barcode-mismatches 1",
                "--fastq-compression-level 6",
            ])
        '''

        # This is how it probably should look

        # FIXME - how do we override "barcode-mismatches"? Needs a design decision.
        # One would hope it could be added to the SampleSheet, under settings, but that's not supported.
        # So we'll need to put it into another settings file.

        self.assertCountEqual(self.bcl2fastq_command_split, [
                "bcl2fastq",
                "-R '%s/%s'" % (self.seqdata_dir, run_id),
                "-o '%s'" % self.out_dir ,
                "--sample-sheet SampleSheet.csv",
                "--use-bases-mask '1:Y300n,I10,Y300n'",
                "--tiles=s_[1]",
                "--barcode-mismatches 1",  # If anything?
                "--fastq-compression-level 6", # Do we still need this? Yes.
            ])


    def test_miseq_badlane(self):
        """What if I try to demux a non-existent lane on a MiSEQ?
        """

        self.assertRaises(KeyError,
                self.run_preprocessor, '150602_M01270_0108_000000000-ADWKV', [1,5]
            )

    def test_hiseq_5_lanes(self):
        """Not sure exactly what is in this HiSeq run?
        """
        run_id = '160607_D00248_0174_AC9E4KANXX'

        #Run with a subset of lanes...
        self.run_preprocessor(run_id, [1,2,3,4,8])

        self.assertEqual(self.pp.lanes, ['1', '2', '3', '4', '8'])

        self.assertCountEqual(self.bcl2fastq_command_split, [
                "bcl2fastq",
                "-R '%s/%s'" % (self.seqdata_dir, run_id),
                "-o '%s'" % self.out_dir ,
                "--sample-sheet SampleSheet.csv",
                "--use-bases-mask '1:Y50n,I8,I8'",
                "--use-bases-mask '2:Y50n,I8,I8'",
                "--use-bases-mask '3:Y50n,I6nn,I8'",
                "--use-bases-mask '4:Y50n,I8,I8'",
                "--use-bases-mask '8:Y50n,I8,I8'",
                "--tiles=s_[12348]",
                "--barcode-mismatches 1",
                "--fastq-compression-level 6",
            ])

    def test_hiseq_all_lanes(self):
        run_id = '160607_D00248_0174_AC9E4KANXX'

        #Run with all lanes...
        self.run_preprocessor(run_id, None)

        self.assertCountEqual(self.bcl2fastq_command_split, [
                "bcl2fastq",
                "-R '%s/%s'" % (self.seqdata_dir, run_id),
                "-o '%s'" % self.out_dir ,
                "--sample-sheet SampleSheet.csv",
                "--use-bases-mask '1:Y50n,I8,I8'",
                "--use-bases-mask '2:Y50n,I8,I8'",
                "--use-bases-mask '3:Y50n,I6nn,I8'",
                "--use-bases-mask '4:Y50n,I8,I8'",
                "--use-bases-mask '5:Y50n,???'",
                "--use-bases-mask '6:Y50n,???'",
                "--use-bases-mask '7:Y50n,???'",
                "--use-bases-mask '8:Y50n,I8,I8'",
                "--tiles=s_[12345678]",
                "--barcode-mismatches 1",
                "--fastq-compression-level 6",
            ])

    # Helper functions
    def run_preprocessor(self, run_name, lanes):
        """Invoke the preprocessor, capture the command line in bcl2fastq_command_string
           and the split-out version in bcl2fastq_command_split
        """
        self.pp = BCL2FASTQPreprocessor( run_dir = os.path.join(self.seqdata_dir, run_name),
                                         lanes = lanes,
                                         dest = self.out_dir )

        self.bcl2fastq_command_split = re.split(r'\s+(?=-)', self.pp.get_bcl2fastq_command())

        """ Stuff related to splitting the sample sheet
        self.bcl2fastq_command_strings = { p : self.pp.get_partial_bcl2fastq_command(p, 'SampleSheet_{}.csv')
                                           for p in self.pp.get_parts() }

        self.bcl2fastq_command_split = { p : re.split(r'\s+(?=-)', cs)
                                         for p, cs in self.bcl2fastq_command_strings.items() }

        self.bcl2fastq_1command_split = None
        if(len(self.bcl2fastq_command_split) == 1):
            self.bcl2fastq_1command_split, = self.bcl2fastq_command_split.values()
        """


### See stuff in /home/mberinsk/workspace/new_raw_data_pipeline/BaseMaskExtractor/tests/

if __name__ == '__main__':
    unittest.main()
