#!/usr/bin/env python3

"""Test the script that produces most of the metadata at the top of
   the HTML reports.
"""

import sys, os, re
import unittest
import logging
import yaml, yamlloader
from collections import OrderedDict
from unittest.mock import patch

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')
EXPECTED_DIR = os.path.abspath(os.path.dirname(__file__) + '/summarize_for_overview')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from summarize_for_overview import get_pipeline_info, get_idict

def sfo_main(run_folder):
    """Version of summarize_for_overview.main that returns the data structure and thus is
       good for testing.
    """
    with open(os.path.join(run_folder, 'pipeline', 'sample_summary.yml')) as rfh:
        rids = yaml.safe_load(rfh)

    # If the pipeline has actually run (demultiplexed) there will be some info about that
    pipeline_info = get_pipeline_info(run_folder)

    # We format everything into an OrderedDict
    return get_idict(rids, run_folder, pipeline_info)

def mock_stat(st_mtime):
    """Returns a version of stat that fudges the .st_mtime to whatever you set
    """
    real_stat = os.stat
    def stat(*args, **kwargs):
        stat_list = list( real_stat(*args, **kwargs) )
        stat_list[8] = st_mtime # item 8 is always os.stat_result.st_mtime
        return os.stat_result(stat_list)
    return stat

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

    def sfo_check(self, run_id):
        """Generic test that loads the existing YAML, runs the check, and
           compares the result.
        """
        with open(os.path.join(EXPECTED_DIR, "run_info.{}.1.yml".format(run_id))) as efh:
            expected = yaml.load(efh, Loader = yamlloader.ordereddict.CSafeLoader)

        got = sfo_main(os.path.join(DATA_DIR, run_id))

        # We need to strip paths from ['Pipeline Script'] and ['Sample Sheet'][1]
        got['pre_start_info']['Pipeline Script'] = os.path.basename(got['pre_start_info']['Pipeline Script'])
        got['pre_start_info']['Sample Sheet'][1] = os.path.basename(got['pre_start_info']['Sample Sheet'][1])

        # Compare dicts - we don't care about order at the top level
        self.assertEqual(dict(expected), got)

    ### THE TESTS ###
    @patch('summarize_for_overview.illuminatus_version', '1.2.3')
    def test_miseq1(self):
        """A run that has not been processed at all
        """
        self.sfo_check("210827_M05898_0165_111111111-JVM38")

    @patch('summarize_for_overview.illuminatus_version', '1.11')
    @patch('os.stat', mock_stat(1630226951))
    def test_miseq2(self):
        """Same but after processing
        """
        self.sfo_check("210827_M05898_0165_000000000-JVM38")

    @patch('summarize_for_overview.illuminatus_version', '1.11')
    @patch('os.stat', mock_stat(1627002191))
    def test_novaseq1(self):
        self.sfo_check("210722_A00291_0378_AHFT2CDRXY")

    @patch('summarize_for_overview.illuminatus_version', 'dummy-version')
    @patch('os.stat', mock_stat(1630767665))
    def test_novaseq2(self):
        """Another example. Here there is a second pipeline number
        """
        self.sfo_check("210903_A00291_0383_BHCYNNDRXY")

if __name__ == '__main__':
    unittest.main()
