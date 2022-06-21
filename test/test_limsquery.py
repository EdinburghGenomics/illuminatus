#!/usr/bin/env python3

"""CHANGEME: Template/boilerplate for writing new test classes"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from illuminatus.LIMSQuery import get_project_names

from collections import namedtuple
from unittest.mock import Mock, patch

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
