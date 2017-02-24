#!/usr/bin/env python3

import sys, os
import unittest

sys.path.insert(0,'.')
from test.binmocker import BinMocker

class TestBinMocker(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
