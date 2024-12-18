#!/usr/bin/env python3

import sys, os, re
import unittest
import logging

from project_real_names import project_real_names, gen_url

class T(unittest.TestCase):

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

    def tearDown(self):
        pass

    ### THE TESTS ###
    def test_name_lookup(self):
        """Test the name lookup logic
        """

        res = project_real_names(['123', '456'], name_list='123_Example_Project')

        # Add the URLs as the script does
        for v in res.values():
            v['url'] = gen_url(v, "T{}T")

        self.assertEqual( res,
                          { '123' : dict( name = "123_Example_Project",
                                          url = "T123_Example_ProjectT" ),
                            '456' : dict( name = "456_UNKNOWN",
                                          error = "not listed in PROJECT_NAME_LIST",
                                          url = "error: not listed in PROJECT_NAME_LIST" ),
                          })

        # TODO - test mock LIMS/RT/Ragic connection


if __name__ == '__main__':
    unittest.main()
