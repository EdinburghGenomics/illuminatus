#!/usr/bin/env python3
import sys, os, re
import unittest
from collections import OrderedDict, Hashable, defaultdict

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')

from illuminatus.YAMLOrdered import yaml

class TestYAMLOrderded(unittest.TestCase):

    adict = OrderedDict([ ('foo', 1),
                          ('bar', 2),
                          ('baz', "Some string"),
                          ('eep', 'a list of strings'.split()),
                          ('oop', dict( another = 'dict')),
            ])

    def setUp(self):
        self.adict_as_yaml = yaml.safe_dump(self.adict)

    def test_tag_order(self):
        adict_as_yaml = self.adict_as_yaml

        #print("Checking all the test tags come out in order...")
        tags = [ tag.split(':')[0] for tag in adict_as_yaml.split('\n') if tag ]

        #print(tags)
        self.assertEqual(tags, ['foo', 'bar', 'baz', 'eep', 'oop'])

    def test_roundtrip(self):
        adict_as_yaml = self.adict_as_yaml

        adict_restored = yaml.load(adict_as_yaml)

        #print("Type %s, length %s" % (type(adict_restored).__name__, len(adict_restored) ))
        self.assertEqual(type(adict_restored), dict)
        self.assertEqual(len(adict_restored), 5)

    def test_defaultdict(self):

        #print("Checking that I can now safe_dump a defaultdict and read back a dict...")
        adefdict = defaultdict(int)
        for n, foo in enumerate('foo bar baz'.split()): adefdict[foo] += n
        adefdict_as_yaml = yaml.safe_dump(adefdict)
        adefdict_restored = yaml.load(adefdict_as_yaml)

        #print(repr(adefdict_restored))
        self.assertEqual(type(adefdict_restored), dict)
        self.assertEqual(adefdict_restored, dict(foo=0, bar=1, baz=2))

if __name__ == '__main__':
    unittest.main()
