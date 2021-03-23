#!/usr/bin/env python3

"""Test the code that prints a basic table of unassigned barcodes from Stats.json"""

import sys, os, re
import unittest
from unittest.mock import patch
import logging
import json

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/stats_json_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

try:
    # This is a safe way to manipulate sys.path without impacting later tests.
    with patch('sys.path', new=['.'] + sys.path):
        from unassigned_to_table import format_lines, make_revcomp_commentor, revcomp, \
                                        get_samples_list
except Exception:
    #If this fails, you is probably running the tests wrongly
    print("****",
          "To test your working copy of the code you should use the helper script:",
          "  ./run_tests.sh <name_of_test>",
          "or to run all tests, just",
          "  ./run_tests.sh",
          "****",
          sep="\n")
    raise

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
    def test_revcomp(self):
        # My basic revcomp had better work
        self.assertEqual( revcomp(''), '' )
        self.assertEqual( revcomp('ATCG'), 'CGAT' )
        self.assertEqual( revcomp('aaaGGGtttNNN'), 'NNNaaaCCCttt' )

    def test_format_lines(self):
        # Load an example file and format it
        with open(DATA_DIR + "/Stats.no10x2.json") as jfh:
            json_data = json.load(jfh)

        lines_out = format_lines(json_data, maxlines=None)
        self.assertEqual( len(lines_out), 1000)

        # Let's just get a few lines
        lines_out = format_lines(json_data, maxlines=4)
        self.assertEqual(lines_out, [ "GCTTCAGG  249100",
                                      "CCCCCCCC  247740",
                                      "GTCCTGGT  213580",
                                      "TTCCTGGG  204620", ])

        # Let's have comments, and see they get added correctly.
        def dummy_commentor(seq, count):
            return "{}/{}".format(seq[:2], count//1000)

        lines_out = format_lines(json_data, maxlines=4, commentor=dummy_commentor)
        self.assertEqual(lines_out, [ "GCTTCAGG  249100  GC/249",
                                      "CCCCCCCC  247740  CC/247",
                                      "GTCCTGGT  213580  GT/213",
                                      "TTCCTGGG  204620  TT/204", ])


    def test_get_samples_list(self):
        # Extract a simple dict from the json_data
        self.assertEqual(get_samples_list({}), {})

        with open(DATA_DIR + "/Stats.no10x2.json") as jfh:
            json_data = json.load(jfh)

        samples_list = get_samples_list(json_data)

        self.assertEqual( samples_list, { "TTCCTGTT": "NoPool__11674BR0001L02",
                                          "CCTTCACC": "NoPool__11674BR0002L02",
                                          "GCCACAGG": "NoPool__11674BR0003L02" } )


if __name__ == '__main__':
    unittest.main()
