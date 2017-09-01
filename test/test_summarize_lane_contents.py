#!/usr/bin/env python3

import unittest
import sys, os
import glob

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')

from summarize_lane_contents import project_real_name


DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')

class T(unittest.TestCase):

    def test_name_lookup(self):

        res = project_real_name(['123', '456'], name_list=['123_Example_Project'])

        #Ignore the url value for now. Or rather, just test it exists.
        self.assertEqual( res,
                          { '123' : dict( name = '123_Example_Project',
                                          url = res['123']['url'] ),
                            '456' : dict( name = '456_UNKNOWN' )        })


if __name__ == '__main__':
    unittest.main()
