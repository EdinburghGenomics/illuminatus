#!/usr/bin/env python3
import unittest
import sys, os, glob, re

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from illuminatus.SampleSheetReader import SampleSheetReader

class TestSampleSheetReader(unittest.TestCase):

    """As far as I can see, SampleSheetReader has one public method:
        get_samplesheet_data_for_BaseMaskExtractor()
            - Returns a dict of {column: [indexlen, indexlen]}

        ** I renamed this to get_index_lengths_by_lane()
    """

    def get_reader_for_sample_sheet(self, run_name):
        """Creates a new reader object from one of our test runs, which live in
           test/seqdata_examples.
        """
        ssfile = os.path.join( os.path.dirname(__file__),
                               'seqdata_examples',
                               run_name,
                               'SampleSheet.csv' )

        return SampleSheetReader(ssfile)

    def test_missing_samplesheet(self):
        """Basic test that the exception gets propogated appropriately.
        """
        self.assertRaises(FileNotFoundError, self.get_reader_for_sample_sheet, 'nosuchrun')

    def test_phix_4000_run(self):
        """Run 160614_K00368_0023_AHF724BBXX has 8 lanes of PhiX.
           We should be able to read that.
        """
        r = self.get_reader_for_sample_sheet('160614_K00368_0023_AHF724BBXX')

        #Do we see all the lanes?
        ilbl = r.get_index_lengths_by_lane()
        self.assertEqual( sorted(ilbl.keys()), list('12345678') )

        #And do they all have zero-length, being dummy indexes?
        self.assertCountEqual( ilbl.values(), [[0,0]] * 8  )


