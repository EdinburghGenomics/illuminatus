#!/usr/bin/env python

"""In get_stat_from_bam.py we find a load of C-style fixed string constants,
   like "HEADER_ELEMENT_INTERNAL_SAMPLE = 'Internal Sample'".
   The rationale here is that having fixed stings in the code is bad, but the
   only reason it is bad (I think) is that if you mis-spell a string then Python
   will not spot the anomaly and just create a new dict key.
   I offer an alternative solution.  A variant of OrderedDict that only stores
   keys you have pre-registered.  And complains loudly if you try to store a
   value against an unregistered key or even to ask about an unregistered key.

   Furthermore, you can't store a value that is already stored without explicitly
   deleting it first.  This guards against accidentally overwriting something
   you already stored with a new value.

   Authored by Tim Booth on 25/2/2016

   Tested with Python2.7 and Python3.4 (see test_fixed_ordered_dict.py)
"""
import collections

#A magic empty list that I define to be NULL
#Only this specific list will pass the (x is _NULL) test
_NULL = []

class DuplicateKeyError(RuntimeError):
    """Raised if you try to register a key twice using add_keys(...),
       or if you try to store a value that is already stored.
    """
    pass

class FixedOrderedDict(collections.MutableMapping):
    """Implements a variant of collections.OrderedDict where you have to register
       keys before you can insert values against them.  Therefore the order of
       the dict is fixed before you start manipulating the data stored in it.

       In normal usage you would make a new FixedOrderedDict object, then run
       set_keys() to register keys, and then use it as an OrderedDict.

       Note - you can only append new keys, not insert or delete them.  I consider
       this to be a feature not a bug.
    """

    #The trick here is that I have a captive OrderedDict
    #that stores references to _NULL by default.  This preserves the
    #distinction between (dict[foo] is None) and (foo not in dict)

    def __init__(self, keys=[], allow_overwrite=False):
        """Keys should be an iterable of keys that you
           want to be able to store in the object.
        """
        #I had used collections.OrderedDict.fromkeys() but this won't
        #object to duplicate keys in the list, so do it this way instead.
        self._innerdict = collections.OrderedDict()
        self.add_keys(*list(keys))

        self.allow_overwrite = allow_overwrite

        #Regular dicts can call __copy__() or equivalently copy() so let's allow that.
        self.copy = self.__copy__

    def add_keys(self, *keys):
        """Add the keys in order to the list of permissable keys.
           Duplicates will trigger a DuplicateKeyError
           Note that there is no way to delete or insert keys.
        """
        for k in keys:
            if k in self._innerdict:
                raise DuplicateKeyError("{} already added".format(k))
            else:
                self._innerdict[k] = _NULL

    def allowed_keys(self):
        """Return all the permissable keys for this instance, be they
           filled or not.
        """
        return self._innerdict.keys()

    def to_dict(self, all_keys=False):
        """Returns a regular OrderedDict.  This will be a copy of the
           _innerdict so you are allowed to take it away and modify it.
           If you want a vanilla unordered dict, just call dict(fod).
        """
        return collections.OrderedDict(
                (key, None if val is _NULL else val)
                for (key, val) in self._innerdict.items()
                if all_keys or (val is not _NULL)
        )

    def keys(self):
        """Return the keys that have something stored, as you would hopefully
           expect.
           ie. This is equivalent to fod.to_dict().keys()
        """
        return [k for (k, v) in self._innerdict.items() if (v is not _NULL)]

    def empty_keys(self):
        """A convenience method, equivalent to
           [ k for k in fod.allowed_keys() if k not in k.keys() ]
        """
        #With direct access to _innerdict we can be slightly more efficient
        #and just do the converse of keys().
        return [ k for (k, v) in self._innerdict.items() if v is _NULL ]


    #def allows_key(self, k):
    #    return (k in self._innerdict)
    # Nope - just use: (k in fod.allowed_keys())

    #def has_key(self, k):
    #    if k not in self._innerdict:
    #        raise KeyError(k)
    #    return self._innerdict[k] is not _NULL
    # Nope - just use: k in fod

    def __len__(self):
        return len(self.keys())

    def __iter__(self):
        return iter(self.to_dict())

    def __setitem__(self, k, v):
        #If the key is not registered you can't store it.
        if k not in self._innerdict:
            raise KeyError(k)

        #Don't go trying to somehow store the magic _NULL token
        assert v is not _NULL

        #If you already stored something you can't just overwrite it.  del it first!
        #Unless allow_overwrite is True
        if (not self.allow_overwrite) and (self._innerdict[k] is not _NULL):
            raise DuplicateKeyError("{} was {}, setting {}".format(k, self._innerdict[k], v))

        self._innerdict[k] = v

    def __delitem__(self, k):
        if k not in self._innerdict:
            raise KeyError(k)

        #Lazy delete, basically
        self._innerdict[k] = _NULL

    def __getitem__(self, k):

        if self._innerdict.get(k) is _NULL:
            raise KeyError(k)

        #This may still raise KeyError if the key
        #is missing completely.
        return self._innerdict[k]

    def get(self, k, default=None):
        #Normally, get() does not raise a KeyError, but I don't
        #even want you to be able to ask about illegal keys.
        if k not in self._innerdict:
            raise KeyError(k)

        #This would be simpler in Py3 as I could just call super()
        return super(FixedOrderedDict,self).get(k, default)

    def __contains__(self, k):
        if k not in self._innerdict:
            raise KeyError(k)

        return self._innerdict[k] is not _NULL

    def __copy__(self):
        #A shallow copy should result in a completely independent
        #object, even though the items stored will not be cloned.
        #This way of doing things is independent of the internal
        #implementation.
        newfod = FixedOrderedDict(self.allowed_keys(), allow_overwrite=self.allow_overwrite)
        for (key, value) in self.items():
            newfod[key] = value
        return newfod
