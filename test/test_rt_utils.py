#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os, glob, re
from tempfile import mkdtemp
from shutil import rmtree, copytree
from io import StringIO
from os import remove

sys.path.insert(0,'.')
from illuminatus.RTUtils import RT_manager

class TestRTUtils(unittest.TestCase):

    def setUp(self):
        pass

    def test_get_RT_server(self):
        self.assertTrue(True)

    def test_get_username_and_password(self):
        self.assertTrue(True)

    def test_get_RT_connection(self):
        self.assertTrue(True)

    def test_find_or_create_run_ticket(self):
        self.assertTrue(True)

    def test_search_run_ticket(self):
        self.assertTrue(True)

    def test_reply_to_ticket(self):
        self.assertTrue(True)

    def test_comment_on_ticket(self):
        self.assertTrue(True)

    def test_change_ticket_status(self):
        self.assertTrue(True)

    def test_change_ticket_subject(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
