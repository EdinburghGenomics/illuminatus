#!/usr/bin/env python3

"""Test the summarize_post_bcl2fastq.py script on some sample run(s)"""

import sys, os, re
import unittest
import logging
import yaml

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/fastqdata_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from summarize_post_bcl2fastq import PostRunMetaData, munge_lanes

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

    def tearDown(self):
        pass

    ### THE TESTS ###
    def test_munge_lanes(self):
        """Mostly just to remind myself what it do.
           Should probably reconsider this func.
        """
        self.assertEqual(munge_lanes([]), {})
        self.assertEqual(munge_lanes(['1']), { 'lanes': ['1'] })
        self.assertEqual(munge_lanes(['overview']), {})
        self.assertEqual(munge_lanes(['lane1','lane2','lane4']), { 'lanes': ['1', '2', '4'] })

    def test_empty(self):

        run_info = PostRunMetaData(DATA_DIR + '/empty', **munge_lanes([]) )

        # The function outputs serialized YAML. That's fine. Convert it back.
        run_info_yaml = yaml.safe_load(run_info.get_yaml())

        # Even for an empty dir we should get something
        self.assertEqual( run_info_yaml,
                          { 'post_demux_info': {
                                'barcode mismatches': 'unknown',
                                'bcl2fastq version': 'unknown' } } )

    def test_novaseq_1(self):
        """This run has 3 lanes, lane 3 just being a copy of lane 1 without the filtered sample sheet.
        """
        run_dir = os.path.abspath(DATA_DIR + '/210129_A00291_0331_BH2V73DRXY')

        # First test with no lanes specified.
        run_info = PostRunMetaData(run_dir)

        # The function outputs serialized YAML. That's fine. Convert it back.
        run_info_yaml = yaml.safe_load(run_info.get_yaml())
        self.assertEqual( run_info_yaml,
                          { 'post_demux_info': {
                                'barcode mismatches': 'standard (1)',
                                'bcl2fastq version': '2.20.0.422' } } )

        # Should be the same if we ask for multiple lanes
        run_info = PostRunMetaData(run_dir, **munge_lanes(['1', '2', '3']) )
        self.assertEqual( yaml.safe_load(run_info.get_yaml()),
                          { 'post_demux_info': {
                                'barcode mismatches': '1',
                                'bcl2fastq version': '2.20.0.422' } } )

        # Now for lanes 1, 2, 3
        run_info = PostRunMetaData(run_dir, lanes = ['1'] )
        self.assertEqual( yaml.safe_load(run_info.get_yaml()),
                          { 'post_demux_info': {
                                'barcode mismatches': '1',
                                'bcl2fastq version': '2.20.0.422',
                                'filtered samplesheet': [ 'SampleSheet.filtered.csv',
                                                          run_dir + '/demultiplexing/lane1/SampleSheet.filtered.csv'],
                                'index revcomp': 'override none' } } )

        run_info = PostRunMetaData(run_dir, lanes = ['2'] )
        self.assertEqual( yaml.safe_load(run_info.get_yaml()),
                          { 'post_demux_info': {
                                'barcode mismatches': '1',
                                'bcl2fastq version': '2.20.0.422',
                                'filtered samplesheet': [ 'SampleSheet.filtered.csv',
                                                          run_dir + '/demultiplexing/lane2/SampleSheet.filtered.csv'],
                                'index revcomp': 'auto 2' } } )

        run_info = PostRunMetaData(run_dir, lanes = ['3'] )
        self.assertEqual( yaml.safe_load(run_info.get_yaml()),
                          { 'post_demux_info': {
                                'barcode mismatches': '1',
                                'bcl2fastq version': '2.20.0.422' } } )

if __name__ == '__main__':
    unittest.main()
