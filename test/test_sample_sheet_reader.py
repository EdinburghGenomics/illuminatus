#!/usr/bin/env python3
import unittest
import sys, os, glob, re

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from illuminatus.SampleSheetReader import SampleSheetReader

class T(unittest.TestCase):

    """As far as I can see, SampleSheetReader has one public method:
        get_samplesheet_data_for_BaseMaskExtractor()
            - Returns a dict of {column: [indexlen, indexlen]}

        ** I renamed this to get_index_lengths_by_lane()
    """
    #Utility funcs
    def get_reader_for_sample_sheet(self, run_name):
        """Creates a new reader object from one of our test runs, which live in
           test/seqdata_examples.
        """
        ssfile = os.path.join( os.path.dirname(__file__),
                               'seqdata_examples',
                               run_name,
                               'SampleSheet.csv' )

        return SampleSheetReader(ssfile)

    #Tests
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

    def test_varied_2500_run(self):
        """Run 160607_D00248_0174_AC9E4KANXX has 8 lanes of various types.
        """
        r = self.get_reader_for_sample_sheet('160607_D00248_0174_AC9E4KANXX')
        ilbl = r.get_index_lengths_by_lane()
        self.assertEqual( sorted(ilbl.keys()), list('12345678') )

        self.assertEqual( ilbl['1'], [8, 8] )
        self.assertEqual( ilbl['2'], [8, 8] )
        self.assertEqual( ilbl['3'], [6, 0] )
        self.assertEqual( ilbl['4'], [8, 0] )
        self.assertEqual( ilbl['5'], [0, 0] )
        self.assertEqual( ilbl['6'], [0, 0] )
        self.assertEqual( ilbl['7'], [0, 0] )
        self.assertEqual( ilbl['8'], [8, 0] )

    def test_miseq_run(self):
        """Run 160603_M01270_0196_000000000-AKGDE has 1 lane, with single barcodes
           length 10
        """
        r = self.get_reader_for_sample_sheet('160603_M01270_0196_000000000-AKGDE')
        ilbl = r.get_index_lengths_by_lane()
        self.assertEqual( sorted(ilbl.keys()), list('1') )

        self.assertEqual( ilbl['1'], [10, 0] )
