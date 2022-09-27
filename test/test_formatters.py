#!/usr/bin/env python3

"""Test the code in illuminatus/Formatters.py"""

import sys, os, re
import unittest
import logging

from datetime import datetime
from illuminatus.Formatters import pct, fmt_time

class T(unittest.TestCase):

    # No setup, these are all pure funcs

    ### THE TESTS ###
    def test_pct(self):

        self.assertEqual( pct(1,200), 0.5 )
        self.assertEqual( pct(11,10), 110.0 )
        self.assertEqual( pct(0,100), 0.0 )
        self.assertEqual( pct(1,3), 100/3 )

        # div by 0. Note that float('nan') does not compare equal to itself
        # so we have to compare strings
        self.assertEqual( str(pct(0,0)), 'nan' )
        self.assertEqual( pct(0,0,nan="Nowt"), 'Nowt' )

    def test_fmt_date(self):

        test_time = datetime.strptime('09/06/18 07:55:26', '%d/%m/%y %H:%M:%S')

        # This was the old format - we just used ctime()
        self.assertEqual( test_time.ctime(), 'Sat Jun  9 07:55:26 2018' )

        # This is the new one. Excel friendly.
        self.assertEqual( fmt_time(test_time), 'Sat 09-Jun-2018 07:55:26' )

if __name__ == '__main__':
    unittest.main()
