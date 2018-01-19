#!/usr/bin/env python3

import sys, os
import unittest

sys.path.insert(0,'.')
from test.binmocker import BinMocker

class T(unittest.TestCase):
    """Internal testing for BinMocker helper
    """
    def test_bin_mocker(self):
        with BinMocker('foo', 'bad') as bm:
            bm.add_mock('bad', fail=True)

            res1 = bm.runscript('true')
            self.assertEqual(res1, 0)
            self.assertEqual(bm.last_stdout, '')
            self.assertEqual(bm.last_stderr, '')
            self.assertEqual(bm.last_calls, bm.empty_calls())
            self.assertEqual(bm.last_calls, dict(foo=[], bad=[]))

            #Now something that actually calls things
            res2 = bm.runscript('echo 123 ; foo foo args ; echo 456 ; ( echo 888 >&2 ) ; bad dog ; bad doggy')
            self.assertEqual(res2, 1)
            self.assertEqual(bm.last_stdout.rstrip().split('\n'), ['123', '456'])
            self.assertEqual(bm.last_stderr.rstrip().split('\n'), ['888'])
            self.assertEqual(bm.last_calls['foo'], ["foo args"])
            self.assertEqual(bm.last_calls['bad'], ["dog", "doggy"])

            #Test that everything resets properly
            res3 = bm.runscript('true')
            self.assertEqual(res3, 0)
            self.assertEqual(bm.last_stdout, '')
            self.assertEqual(bm.last_stderr, '')
            self.assertEqual(bm.last_calls, dict(foo=[], bad=[]))

    def test_side_effect(self):
        """New feature - we can add a side_effect to our mock.
        """
        bm = BinMocker()
        self.addCleanup(bm.cleanup)

        #Side effect should happen but should not affect the return value.
        bm.add_mock('this', side_effect="echo THIS ; false")
        bm.add_mock('that', side_effect="echo THAT >&2 ; true", fail=True)

        res1 = bm.runscript('this')
        self.assertEqual(res1, 0)
        self.assertEqual(bm.last_stdout, 'THIS\n')

        res2 = bm.runscript('that')
        self.assertEqual(res2, 1)
        self.assertEqual(bm.last_stderr, 'THAT\n')

    def test_mock_abs_path(self):
        """It should be possible to mock out even commands referred to by
           full path. Note that this will only work for things called from
           BASH, not for things called indirectly like "env /bin/foo".
        """
        bm = BinMocker()
        self.addCleanup(bm.cleanup)

        bm.add_mock('/bin/false', side_effect="echo THIS")

        res1 = bm.runscript('/bin/false 123')
        self.assertEqual(res1, 0)
        self.assertEqual(bm.last_calls['/bin/false'], ['123'])
        self.assertEqual(bm.last_stdout, 'THIS\n')

        #Should also work if called from a sub-script.
        bm.add_mock('woo',  side_effect="/bin/false 789")
        bm.add_mock('/bin/wibble',  side_effect="woo 456")

        res2 = bm.runscript('/bin/wibble 123')
        self.assertEqual(bm.last_calls['/bin/wibble'], ['123'])
        self.assertEqual(bm.last_calls['woo'], ['456'])
        self.assertEqual(bm.last_calls['/bin/false'], ['789'])
        self.assertEqual(bm.last_stdout, 'THIS\n')

        #Referring to a command stored in a var is OK
        res3 = bm.runscript('cmd=/bin/false ; "$cmd" 123')
        self.assertEqual(res3, 0)
        self.assertEqual(bm.last_stdout, 'THIS\n')

        #But calling a command via 'env' does call the actual command
        res4 = bm.runscript('env /bin/false 123')
        self.assertEqual(res4, 1)
        self.assertEqual(bm.last_stdout, '')

if __name__ == '__main__':
    unittest.main()
