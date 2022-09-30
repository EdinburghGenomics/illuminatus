#!/usr/bin/env python3

"""Test the code in illuminatus/Formatters.py"""

import sys, os, re
import unittest
import logging
from math import isnan

from datetime import datetime
from illuminatus.Formatters import pct, fmt_time, fmt_duration

class T(unittest.TestCase):

    # No setup, these are all pure funcs

    ### THE TESTS ###
    def test_pct(self):

        self.assertEqual( pct(1,200), 0.5 )
        self.assertEqual( pct(11,10), 110.0 )
        self.assertEqual( pct(0,100), 0.0 )
        self.assertEqual( pct(1,3), 100/3 )

        # div by 0. Note that float('nan') does not compare equal to itself
        # so we have to use the camparison method
        self.assertTrue( isnan(pct(0,0)) )
        self.assertEqual( pct(0,0,nan="Nowt"), 'Nowt' )

    def test_fmt_date(self):

        test_time = datetime.strptime('09/06/18 07:55:26', '%d/%m/%y %H:%M:%S')

        # This was the old format - we just used ctime()
        self.assertEqual( test_time.ctime(), 'Sat Jun  9 07:55:26 2018' )

        # This is the new one. Excel friendly.
        self.assertEqual( fmt_time(test_time.timestamp()), 'Sat 09-Jun-2018 07:55:26' )

    def test_fmt_duration(self):

        test_time1 = datetime.strptime('09/06/18 07:55:26', '%d/%m/%y %H:%M:%S')
        test_time2 = datetime.strptime('09/06/18 08:45:00', '%d/%m/%y %H:%M:%S')
        test_time3 = datetime.strptime('11/06/18 15:00:00', '%d/%m/%y %H:%M:%S')
        test_time4 = datetime.strptime('11/06/18 16:00:00', '%d/%m/%y %H:%M:%S')

        self.assertEqual( fmt_duration(test_time1.timestamp(), test_time2.timestamp()),
                          "0 hours 49 minutes" )
        self.assertEqual( fmt_duration(test_time2.timestamp(), test_time3.timestamp()),
                          "54 hours 15 minutes" )
        self.assertEqual( fmt_duration(test_time1.timestamp(), test_time3.timestamp()),
                          "55 hours 04 minutes" )
        self.assertEqual( fmt_duration(test_time3.timestamp(), test_time4.timestamp()),
                          "1 hours 00 minutes" )

        # We shouldn't ever get negative durations but I should account for the possibility
        self.assertEqual( fmt_duration(test_time3.timestamp(), test_time1.timestamp()),
                          "invalid negative duration" )

        # If called with one arg, we get the time from then til now
        self.assertEqual( fmt_duration(datetime.now().timestamp()), "0 hours 00 minutes" )

if __name__ == '__main__':
    unittest.main()
