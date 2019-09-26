#!/usr/bin/env python3

import sys, os
import unittest
from unittest.mock import patch

with patch('sys.path', new=['.'] + sys.path):
    from grab_bcl2fastq_stats import gather_fastq_stats

TESTDIR = os.path.abspath(os.path.dirname(__file__))

class T(unittest.TestCase):

    def test_simple_parse(self):

        testfile = TESTDIR + '/fastqsummary_sample/FastqSummaryF1L8.txt'

        metrics = gather_fastq_stats(testfile)
        m = { k: (round(v, 6) if type(v) is float else v) for k, v in metrics.items() }

        #I calculated these values using the program in the first place,
        #so this is only a regression test.
        self.assertEqual(m['Assigned Reads PF'],        51381735)
        self.assertEqual(m['Unassigned Reads Raw'],     17616585)
        self.assertEqual(m['Unassigned Reads PF'],      4368690)
        self.assertEqual(m['Fraction PF'],              0.807997)
        self.assertEqual(m['Fraction Assigned'],        0.744681)
        self.assertEqual(m['Mean Reads Per Sample'],    1657475.322581)
        #This changed as I found out that Illumina use a slightly different calculation
        #for the barcode balance.
        # self.assertEqual(m['Barcode Balance'],          0.583384)
        self.assertEqual(m['Barcode Balance'],          0.593027)

    def test_one_sample(self):

        # Previously the stats got messed up if you only had one sample.
        testfile = TESTDIR + '/fastqsummary_sample/FastqSummaryF1L7.txt'

        metrics = gather_fastq_stats(testfile)
        m = { k: (round(v, 6) if type(v) is float else v) for k, v in metrics.items() }

        #Now it should report the barcode balance is NA
        self.assertEqual(m['Barcode Balance'],          'NA')

if __name__ == '__main__':
    unittest.main()
