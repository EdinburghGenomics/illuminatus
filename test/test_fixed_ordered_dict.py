#!/usr/bin/env python3

import unittest
import copy
import collections

# Adding this to sys.path makes the test work if you just run it directly.
import sys
sys.path.insert(0,'.')

from illuminatus.FixedOrderedDict import FixedOrderedDict, DuplicateKeyError

class TestFixedOrderedDict(unittest.TestCase):
    """Sorry, the order of these tests is somewhat arbitrary.
    """

    #Needed in order to let assertRaises trap the exception.
    def _setitem(self, adict, akey, aval):
        adict[akey] = aval

    def _keyindict(self, adict, akey):
        return akey in adict

    def test_basics(self):
        # I want an object that behaves like a dict() but:
        foo = FixedOrderedDict()

        # foo['bar'] = 123 # Raises KeyError
        self.assertRaises(KeyError, self._setitem, foo, 'bar', 123)

        foo.add_keys('bar') # OK

        self.assertEqual(foo.get('bar', 'nope'), 'nope') # Missing key

        foo['bar'] = 123 # OK
        self.assertEqual(foo.get('bar', 'nope'), 123) # OK

        del(foo['bar'])
        foo['bar'] = None # OK
        self.assertEqual(foo.get('bar', 'nope'), None) # OK

        self.assertRaises(DuplicateKeyError, foo.add_keys, 'bar') # Raise DuplicateKeyError

        foo.add_keys('bam', 'oop')
        foo['oop'] = 456

        self.assertEqual(foo['oop'], 456)

        self.assertEqual(list(foo), ['bar', 'oop'])
        self.assertEqual(list(foo.keys()), ['bar', 'oop'])
        self.assertEqual(list(foo.allowed_keys()), ['bar', 'bam', 'oop'])

        self.assertEqual(len(foo), 2)
        del(foo['bar']) # removes it but remembers the key is acceptable
        self.assertEqual(len(foo), 1)

        self.assertEqual(list(foo), ['oop'])
        self.assertEqual(list(foo.allowed_keys()), ['bar', 'bam', 'oop'])

        #foo.to_dict() # Returns the whole thing as an ordereddict
        self.assertEqual(foo.to_dict(),
                         collections.OrderedDict( [('oop', 456)] )
                        )

        #foo.ordereddict(all_keys = 1) # Returns the whole thing as an orderedict
        #but with the hidden keys set to None.
        self.assertEqual(foo.to_dict(all_keys=True),
                         collections.OrderedDict( [('bar', None), ('bam', None), ('oop', 456)] )
                        )

    def test_construction(self):

        #1 Constrctor with keys should work
        fod1 = FixedOrderedDict('key1 key2 key3'.split())
        self.assertEqual(list(fod1.allowed_keys()), 'key1 key2 key3'.split())

        #2 Duplicates should fail
        self.assertRaises(DuplicateKeyError, FixedOrderedDict, 'key1 key2 key1'.split())

        #3 Copy should work
        fod3 = copy.copy(fod1)
        fod3.add_keys('key4')

        self.assertEqual(list(fod3.allowed_keys()), 'key1 key2 key3 key4'.split())

        fod3['key1'] = 888
        fod3['key4'] = 444

        #fod1 should still have 3 keys and no values
        self.assertEqual(len(fod1.allowed_keys()), 3)
        self.assertEqual(len(fod1), 0)

        #4 Copy empty should work
        fod1['key1'] = 111
        fod1['key2'] = 222
        fod4 = FixedOrderedDict(fod1.allowed_keys())

        self.assertEqual(len(fod1), 2)
        self.assertEqual(len(fod4), 0)
        self.assertEqual(list(fod4.allowed_keys()), 'key1 key2 key3'.split())

        #5 Copy should work this way too
        fod1.clear()
        fod5 = fod1.copy()
        fod5.add_keys('key4')

        self.assertEqual(list(fod3.allowed_keys()), 'key1 key2 key3 key4'.split())

        fod5['key1'] = 888
        fod5['key4'] = 444

        #fod1 should still have 3 keys and no values
        self.assertEqual(len(fod1.allowed_keys()), 3)
        self.assertEqual(len(fod1), 0)

    def test_presence_absence(self):

        fod1 = FixedOrderedDict('key1 key2 key3'.split())
        fod1['key1'] = None
        fod1['key2'] = 123

        self.assertTrue('key1' in fod1)
        self.assertFalse(fod1['key1'])

        #has_key() was retired from Py3, so we don't need it
        #self.assertTrue(fod1.has_key('key1'))
        #self.assertRaises(KeyError, fod1.has_key, 'key0')

        #Likewise, get() should object when asked for an illegal key
        self.assertRaises(KeyError, fod1.get, 'key0', 'default')

        #And for consistency 'in' should do the same.  This traps issues like:
        # if "Improttant Data" not in my_dict:
        #     my_dict["Important Data"] = 1234
        self.assertRaises(KeyError, self._keyindict, fod1, 'key0')

        # Talking of in, I just want to be sure this works as expected...
        self.assertEqual([ k for k in fod1.keys() ],
                         [ k for k in fod1 ])

        #And also the empty_keys() convenience method
        self.assertEqual( list(fod1.empty_keys()), ['key3'] )

    def test_no_overwrite(self):
        """By default you can only set things once, unless you explicitly
           delete and re-add.
        """

        fod1 = FixedOrderedDict('key1 key2 key3'.split())

        fod1['key1'] = 123
        self.assertRaises(DuplicateKeyError, self._setitem, fod1, 'key1', 123)

        #But I can delete and re-insert...
        del(fod1['key1'])
        fod1['key1'] = 888

        self.assertEqual( list(fod1.values()), [888] )

        #For the avoidance of doubt, even storing None on top of None counts as a
        #duplicate write.
        fod1['key2'] = None
        self.assertRaises(DuplicateKeyError, self._setitem, fod1, 'key2', None)

    def test_allow_overwrite(self):
        """Overwrite protection can be turned off if you don't want it.
        """

        fod1 = FixedOrderedDict('key1 key2 key3'.split(), allow_overwrite=True)

        fod1['key1'] = 123
        fod1['key1'] = 123

        self.assertEqual( list(fod1.values()), [123] )

        fod1['key1'] = 888

        self.assertEqual( list(fod1.values()), [888] )

if __name__ == '__main__':
    unittest.main()
