#!/usr/bin/env python3

"""CHANGEME: Template/boilerplate for writing new test classes"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

from collections import namedtuple
from unittest.mock import Mock, patch

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

# We want to prevent imports of psycopg2 and pyclarity_lims for the purposes of this test,
# so that the CI builder doens't need to install them to run the test.
sys.modules.update( { 'psycopg2': Mock(),
                      'psycopg2.extras': Mock().extras,
                      'psycopg2.extensions': Mock().extensions,
                      'pyclarity_lims.lims': Mock().lims } )
from illuminatus.LIMSQuery import get_project_names

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        logging.basicConfig()
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

    @patch("illuminatus.LIMSQuery.MyLimsDB")
    def test_get_project_names(self, mock_limsdb):
        """I added this because I carelessly introduced a bug in the function.
           Use patching to decouple the thing from the actual LIMS API
        """
        # Prior to fixing the return val we get [None] because iterating over a MagicMock
        # yields an empty iterator.
        self.assertEqual(get_project_names('12345'), [None])


        Record = namedtuple("Record", ["name"])
        mock_limsdb().__enter__().select.return_value = [ Record(name='12345_Foo_Bar'),
                                                          Record(name='12345_test_ignoreme') ]

        # The test value should be ignored by filter_names() we should get a good result.
        self.assertEqual(get_project_names('12345'), ["12345_Foo_Bar"])

if __name__ == '__main__':
    unittest.main()
