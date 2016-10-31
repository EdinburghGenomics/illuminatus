#!/usr/bin/env python3

import unittest
import sys, os
from glob import glob

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')

from illuminatus.BaseMaskExtractor import BaseMaskExtractor

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/base_mask_examples')

class TestBaseMaskExtractor(unittest.TestCase):

    def bm_test(self, subdir):
        """Given the name of a folder in DATA_DIR, check that the generated
           base mask matches the expected one for all lanes.
           Anything with a mask of 'AMBIGUOUS' should raise an exception.
        """
        lanes = {}
        with open(os.path.join(DATA_DIR, subdir, 'lanemasks.txt')) as lfh:
            lanes.update(l.strip().split() for l in lfh)

        #There should always be at least a lane 1
        self.assertTrue(lanes['1'])

        ss  = os.path.join( DATA_DIR, subdir, "SampleSheet.csv" )
        rif = os.path.join( DATA_DIR, subdir, "RunInfo.xml" )

        bme = BaseMaskExtractor( ss , rif )
        for lane, expected_bm in lanes.items():
            if expected_bm == 'AMBIGUOUS':
                self.assertRaises(ValueError, bme.get_base_mask_for_lane, lane)
            else:
                self.assertEqual(expected_bm, bme.get_base_mask_for_lane(lane))

    #Tests get added dynamically

"""
print(vars(TestBaseMaskExtractor))

for i, n in enumerate([ True, True, False ]):
    #Note the slightly contorted double-lambda syntax to make the closure.
    setattr(TestBaseMaskExtractor, 'test_bme_%i' % i, (lambda n: lambda self: self.assertTrue(n))(n))
"""
# Now add the tests dynamically
for lm in glob(os.path.join(DATA_DIR, '*', 'lanemasks.txt')):
    #Note the slightly contorted double-lambda syntax to make the closure.
    dname = os.path.basename(os.path.dirname(lm))
    setattr(TestBaseMaskExtractor, 'test_bme_%s' % dname, (lambda d: lambda self: self.bm_test(d))(dname))

if __name__ == '__main__':
    unittest.main()

