#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch
import sys, os
from io import StringIO

from rt_runticket_manager import RTManager, AuthorizationError, main

RT_SETTINGS = os.path.abspath(os.path.dirname(__file__) + '/rt_settings.ini')

class T(unittest.TestCase):

    def setUp(self):
        os.environ['RT_SETTINGS'] = RT_SETTINGS
        try:
            del os.environ['RT_SYSTEM']
        except Exception:
            pass

    @patch('rt_runticket_manager.Rt')
    def mock_connect(self, queue, mock_rt):
        """Mock connection with test-rt settings from the sample .ini file.

           Returns an RTManager instance where rtman.tracker is a MagicMock.
        """
        rtman = RTManager('test-rt', queue_setting=queue)
        rtman.connect()

        # Not sure if I need to do this but it does work.
        rtman.tracker.mock_parent = mock_rt
        return rtman

    def test_connect(self):
        """Test that the class attempts to make an RT connection as expected..
        """

        mc = self.mock_connect('default')

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
        rtman = RTManager('test-rt', queue_setting='default')
        c = rtman._config

        self.assertEqual( c.get('run_cc'), '' )
        self.assertEqual( c.get('requestor'), 'pipeline' )
        self.assertEqual( c.get('user'), 'pipeline' )
        self.assertEqual( c.get('pass'), 'test' )

        c2 = RTManager('production-rt', queue_setting='run')._config
        self.assertEqual( c2.get('user'), 'UNSET' )
        self.assertEqual( len(c2.get('qc_cc').split(",")), 5 )

        # And if the section is invalid?
        self.assertRaises(AuthorizationError, RTManager, 'no-such-rt', queue_setting='run')
        self.assertRaises(AuthorizationError, RTManager, 'production-rt', queue_setting='no-such-queue')

        # And if the config file was not found?
        os.environ['RT_SETTINGS'] = '/no/such/file'
        self.assertRaises(AuthorizationError, RTManager, 'test-rt', queue_setting='run')

    def test_search_run_ticket(self):

        rtman = self.mock_connect('default')

        #Poke a result into the mock object.
        rtman.tracker.search.return_value = [ dict( Subject = "Run 9999_8888 foo",
                                                    id = "ticket/1234" ) ]
        res = rtman.search_run_ticket("9999_8888")
        #We now open the tickets.
        rtman.tracker.search.assert_called_with(Queue = "bfx-general", Subject__like='%9999_8888%', Status='open')
        self.assertEqual( res,
                          (1234, {'id': 'ticket/1234', 'Subject': 'Run 9999_8888 foo'}) )

    def test_find_or_create_run_ticket(self):

        rtman = self.mock_connect('run')
        rtman.tracker.create_ticket.return_value = 4044

        rtman.find_or_create_run_ticket("blah_run", "my subject", text = "1\n2\n3\n")

        #The ticket won't be found so should be created with the
        #subject specified.
        #Also the Text should be munged to work around a bug in the rt.py module.
        rtman.tracker.create_ticket.assert_called_with(
                        Subject   = "my subject",
                        Queue     = "bfx-run",
                        Requestor = "pipeline",
                        Cc        = "",
                        Text      = "1\n      2\n      3" )

        #What I can't test here is whether the real Rt returns a string or an int :-/

        # Ticket should now be opened after creation
        rtman.tracker.edit_ticket.assert_called_with( 4044, Status='open' )

    ### Not adding test coverage to these for now as they are pretty simple.
    # def test_reply_to_ticket(self):
    #    self.assertTrue(True)
    #
    # def test_comment_on_ticket(self):
    #     self.assertTrue(True)
    #
    # def test_change_ticket_status(self):
    #     self.assertTrue(True)
    #
    # def test_change_ticket_subject(self):
    #     self.assertTrue(True)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.stderr', new_callable=StringIO)
    def test_dummy_ticket_query(self, dummy_stdout, dummy_stderr):
        """ This test calls the main function, so it serves as a test of that.
            When in dummy mode, the program should print a warning and it should tell
            us that whatever ticket we look for is actually 999.
        """
        args = Mock()
        args.run_id = "SOME_RUN"
        args.queue = "default"
        args.reply = args.comment = args.subject = args.status = None
        args.no_create = False
        args.test = False

        # Make the library not connect (but not by Mocking it)
        os.environ['RT_SYSTEM'] = 'none'

        self.assertRaisesRegex(SystemExit, "Ticket #999 for 'SOME_RUN' has subject: None", main, args)

        self.assertEqual(dummy_stderr.getvalue(), '')
        self.assertEqual(dummy_stdout.getvalue()[:23], 'Making dummy connection')

if __name__ == '__main__':
    unittest.main()
