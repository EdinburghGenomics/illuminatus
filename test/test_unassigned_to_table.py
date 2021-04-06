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
        self.assertEqual(lines_out, [ "GCTTCAGG  249100".replace("  ", "\t"),
                                      "CCCCCCCC  247740".replace("  ", "\t"),
                                      "GTCCTGGT  213580".replace("  ", "\t"),
                                      "TTCCTGGG  204620".replace("  ", "\t"), ])

        # Let's have comments, and see they get added correctly.
        def dummy_commentor(seq, count):
            return [ "{}/{}".format(seq[:2], count//1000) ]

        lines_out = format_lines(json_data, maxlines=4, commentor=dummy_commentor)
        self.assertEqual(lines_out, [ "GCTTCAGG  249100  GC/249".replace("  ", "\t"),
                                      "CCCCCCCC  247740  CC/247".replace("  ", "\t"),
                                      "GTCCTGGT  213580  GT/213".replace("  ", "\t"),
                                      "TTCCTGGG  204620  TT/204".replace("  ", "\t"), ])


    def test_get_samples_list(self):
        # Extract a simple dict from the json_data
        self.assertEqual(get_samples_list({}), {})

        with open(DATA_DIR + "/Stats.no10x2.json") as jfh:
            json_data = json.load(jfh)

        samples_list = get_samples_list(json_data)

        self.assertEqual( samples_list, { "TTCCTGTT": "NoPool__11674BR0001L02",
                                          "CCTTCACC": "NoPool__11674BR0002L02",
                                          "GCCACAGG": "NoPool__11674BR0003L02" } )

    def test_make_revcomp_commentor(self):
        # This function takes a dict as output by get_samples_list() and returns
        # a new function f(seq, *_) that points out likely reverse complement matches.

        # Empty case. Should this add any message at all? I think not.
        empty_commentor = make_revcomp_commentor({})
        self.assertEqual( empty_commentor('ATC', 1), [] )

        # Basic list with single barcodes as above
        single_barcode_samples = { "TTCCTGTT": "NoPool__11674BR0001L02",
                                   "CCTTCACC": "NoPool__11674BR0002L02",
                                   "GCCACAGG": "NoPool__11674BR0003L02" }

        sb_commentor = make_revcomp_commentor(single_barcode_samples)
        # We shouldn't ever see an exact match in a real file, but logically I should say something
        # Other than that we have only 2 cases, and we want to have the pool name snipped off in comments.
        # Note the expected return val here is a single-item list.
        self.assertEqual( sb_commentor("TTCCTGTT"), ["is 11674BR0001L02"] )
        self.assertEqual( sb_commentor(revcomp("TTCCTGTT")), ["revcomp of 11674BR0001L02"] )
        self.assertEqual( sb_commentor("TGGGGGGG"), [] )

        # Now for dual barcodes we have more possibilities
        dual_barcode_samples = { "ATT+ACC": "sample1",
                                 "ATT+CTT": "sample2",
                                 "CAT+TAG": "sample3",
                                 "CAT+AGA": "sample4",
                                 "ATG+TCT": "sample5",
                                 "ATG+AGA": "sample6"}

        db_commentor = make_revcomp_commentor(dual_barcode_samples)
        # 1. no match at all
        self.assertEqual( db_commentor("AAA+AAA"), [] )
        # 2. exact match (as noted above, should never be seen)
        self.assertEqual( db_commentor("CAT+TAG"), ["is sample3"] )
        # 3. match after index2 revcomp
        self.assertEqual( db_commentor("CAT+CTA"), ["revcomp idx2 of sample3"] )
        # 4. match after index1 revcomp
        self.assertEqual( db_commentor("ATG+TAG"), ["revcomp idx1 of sample3"] )
        # 5. match after double revcomp
        self.assertEqual( db_commentor("ATG+CTA"), ["revcomp idx1+2 of sample3"] )
        # 6. match after index2 revcomp OR index1 revcomp OR both
        # Note this is starting to look like the old unassigned reads reporter which spewed out
        # loads of possible barcode IDs, but this is only looking at codes within the lane so this
        # kind or result should be very rare.
        self.assertEqual( db_commentor("CAT+TCT"), ["revcomp idx1 of sample5; revcomp idx2 of sample4; revcomp idx1+2 of sample6"] )

if __name__ == '__main__':
    unittest.main()
