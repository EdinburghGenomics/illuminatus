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

    def test_4k_runinfo(self):
        """ Since we no longer use the 4000, I have not added the flowcell type to the list.
        """
        rip = RunInfoXMLParser( DATA_DIR + '/160614_K00368_0023_AHF724BBXX' )
        self.assertEqual(rip.run_info['FCType'], '8/2/2/28')

if __name__ == '__main__':
    unittest.main()
