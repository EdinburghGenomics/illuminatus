class aggregator:
    """A light wrapper around a list to save some typing when building
       a list of lines to be printed.
    """
    def __init__(self, *args, ofs=None):
        self._list = list()
        self._ofs = ofs
        if args:
            self(*args)

    def __call__(self, *args):
        if self._ofs:
            self._list.append(self._ofs.join([str(a) for a in args]))
        else:
            # Add multipe lines (same as ofs="\n")
            self._list.extend([str(a) for a in args] or [''])

    def __iter__(self, *args):
        return iter(self._list)

