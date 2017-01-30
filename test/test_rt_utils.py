#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os

sys.path.insert(0,'.')
from illuminatus.RTUtils import RT_manager

from rt import AuthorizationError

RT_SETTINGS = os.path.abspath(os.path.dirname(__file__) + '/rt_settings.ini')

class TestRTUtils(unittest.TestCase):

    def setUp(self):
        os.environ['RT_SETTINGS'] = RT_SETTINGS

    @patch('rt.Rt')
    def mock_connect(self, mock_rt):
        """Mock connection with test-rt settings from the sample .ini file.

           Returns an RT_manager instance where rtman.tracker is a MagicMock.
        """
        rtman = RT_manager('test-rt')
        rtman.connect()
        rtman.tracker.mock_parent = mock_rt
        return rtman

    def test_connect(self):
        """Test that the class attempts to make an RT connection as expected..
        """

        mc = self.mock_connect()

        #Look at mock_parent to see how the class was instantiated.
        mc.tracker.mock_parent.assert_called_with(
                                    'http://rt-test.genepool.private/REST/1.0',
                                    'pipeline',
                                    'test',
                                    default_queue = 'bfx-general')
        #Login should have been called with no args.
        mc.tracker.login.assert_called_with()


    def test_get_config_from_ini(self):
        """Test that the configuration looks as expected.
        """
        rtman = RT_manager('test-rt')
        c = rtman._config

        self.assertEqual( c.get('run_cc'), '' )
        self.assertEqual( c.get('requestor'), 'pipeline' )
        self.assertEqual( c.get('user'), 'pipeline' )
        self.assertEqual( c.get('pass'), 'test' )

        c2 = RT_manager('production-rt')._config
        self.assertEqual( c2.get('user'), 'UNSET' )
        self.assertEqual( len(c2.get('qc_cc').split(",")), 5 )

        # And if the section is invalid?
        self.assertRaises(AuthorizationError, RT_manager, 'no-such-rt')

        # And if the config file was not found?
        os.environ['RT_SETTINGS'] = '/no/such/file'
        self.assertRaises(AuthorizationError, RT_manager, 'test-rt')

    def test_search_run_ticket(self):

        rtman = self.mock_connect()

        #Poke a result into the mock object.
        rtman.tracker.search.return_value = [ dict( Subject = "Run 9999_8888 foo",
                                                    id = "ticket/1234" ) ]
        res = rtman.search_run_ticket("9999_8888")
        rtman.tracker.search.assert_called_with(Queue = "bfx-run")
        self.assertEqual(res, 1234)

        #And for a run that isn't in the list
        res = rtman.search_run_ticket("0000_0000")
        self.assertEqual(res, None)

    def test_find_or_create_run_ticket(self):

        rtman = self.mock_connect()

        rtman.find_or_create_run_ticket(1234, "my subject")

        #The ticket won't be found so should be created with the
        #subject specified.
        rtman.tracker.create_ticket.assert_called_with(
                        Subject   = "my subject",
                        Queue     = "bfx-run",
                        Requestor = "pipeline",
                        Cc        = "",
                        Text      = "" )

        #What I can't test here is whether the real Rt returns a string or an int.

    '''
    # Not adding test coverage to these for now as they are pretty simple.
    def test_reply_to_ticket(self):
        self.assertTrue(True)

    def test_comment_on_ticket(self):
        self.assertTrue(True)

    def test_change_ticket_status(self):
        self.assertTrue(True)

    def test_change_ticket_subject(self):
        self.assertTrue(True)
    '''

if __name__ == '__main__':
    unittest.main()
