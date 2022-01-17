#!/usr/bin/env python3

import unittest
import sys, os

from illuminatus.RunInfoXMLParser import RunInfoXMLParser

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

class T(unittest.TestCase):

    def test_miseq_runinfo1(self):
        """ A MiSeq example
        """
        rip = RunInfoXMLParser( DATA_DIR + '/150602_M01270_0108_000000000-ADWKV' )
        self.assertEqual(rip.run_info, {
                            'Cycles': '301 [8] 301',
                            'Flowcell': 'ADWKV',
                            'FCType': 'Normal v3',
                            'Instrument': 'miseq_M01270',
                            'LaneCount': 1,
                            'RunDate': '2015-06-02',
                            'RunId': '150602_M01270_0108_000000000-ADWKV'
        })
        self.assertEqual(rip.tiles, [])

    def test_miseq_runinfo2(self):
        """ A newer MiSeq example
        """
        rip = RunInfoXMLParser( DATA_DIR + '/180430_M05898_0007_000000000-BR92R' )
        self.assertEqual(rip.run_info, {
                            'Cycles': '26 [8] [8] 26',
                            'Flowcell': 'BR92R',
                            'FCType': 'Normal v2',
                            'Instrument': 'miseq_M05898',
                            'LaneCount': 1,
                            'RunDate': '2018-04-30',
                            'RunId': '180430_M05898_0007_000000000-BR92R'
        })
        self.assertEqual(rip.tiles, [])

    def test_novaseq_runinfo(self):
        """ A (more recent) NovaSeq example
        """
        rip = RunInfoXMLParser( DATA_DIR + '/180619_A00291_0044_BH5WJJDMXX' )
        self.assertEqual(rip.run_info, {
                            'Cycles': '51 [8] [8] 51',
                            'Flowcell': 'H5WJJDMXX',
                            'FCType': 'S2',
                            'Instrument': 'novaseq_A00291',
                            'LaneCount': 2,
                            'RunDate': '2018-06-19',
                            'RunId': '180619_A00291_0044_BH5WJJDMXX'
        })

        # We have 1408 tiles split evenly over 2 lanes
        self.assertEqual(rip.tiles[0], '1_1101')
        self.assertEqual(rip.tiles[704], '2_1101')
        self.assertEqual(rip.tiles[1407], '2_2488')
        self.assertEqual(len(rip.tiles), 1408)

    def test_rixp_date_bug(self):
        """ Turns out that dates before the 10th of the month were being mangled.
            Oops.
            Note this flowell is XP but the RIXP calls it as S1 because it doesn't look
            at the RunParameters file - this is expected.
        """
        rip = RunInfoXMLParser( DATA_DIR + '/210601_A00291_0371_AHF2HCDRXY' )
        self.assertEqual(rip.run_info, {
                            'Cycles': '51 [8] [8] 51',
                            'Flowcell': 'HF2HCDRXY',
                            'FCType': 'S1', # But not really
                            'Instrument': 'novaseq_A00291',
                            'LaneCount': 2,
                            'RunDate': '2021-06-01',
                            'RunId': '210601_A00291_0371_AHF2HCDRXY'
        })

        # Also with an SP flowcell we have 312 tiles
        self.assertEqual(rip.tiles[0], '1_2101')
        self.assertEqual(rip.tiles[156], '2_2101')
        self.assertEqual(len(rip.tiles), 312)


    def test_4k_runinfo(self):
        """ Since we no longer use the 4000, I have not added the flowcell type to the list.
        """
        rip = RunInfoXMLParser( DATA_DIR + '/160614_K00368_0023_AHF724BBXX' )
        self.assertEqual(rip.run_info['FCType'], '8/2/2/28')

if __name__ == '__main__':
    unittest.main()
