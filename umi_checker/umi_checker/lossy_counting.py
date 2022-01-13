"""Lossy Counting in pure Python

   https://gist.github.com/giwa/bce63f3e2bd493167d92

   Updated for Python3 by Tim
"""

from collections import defaultdict
from math import log
import logging

L = logging.getLogger(__name__)

class LossyCounter(object):
    'Implemendation of Lossy Counting'

    # I think epsilon represents the lowest fraction of the items that can reasonably be detected.

    def __init__(self, epsilon=5e-3):
        self._n = 0
        self._count = defaultdict(int)
        self._bucket_id = dict()
        self._epsilon = epsilon
        self._current_bucket_id = 1

    def get_count(self, item):
        """Return the number of the item
        """
        return self._count[item]

    def get_n(self):
        return self._n

    def get_bucket_id(self, item):
        """Return the bucket id corresponding to the item
        """
        return self._bucket_id[item]

    def add_count(self, item):
        """Add item for counting
        """
        self._n += 1
        if item not in self._count:
            self._bucket_id[item] = self._current_bucket_id - 1
        self._count[item] += 1

        if self._n % int(1 / self._epsilon) == 0:
            self._trim()
            self._current_bucket_id += 1

    def get_iter_with_threshold_rate(self, threshold_rate):
        return self.get_iter(threshold_rate * self._n)

    def _trim(self):
        """trim data which does not fit the criteria
        """
        removal_list = []
        for item, total in self._count.items():
            if total <= self._current_bucket_id - self._bucket_id[item]:
                removal_list.append(item)
        for item in removal_list:
            del self._count[item]
            del self._bucket_id[item]

    def get_iter(self, threshold_count=None):
        """Extract the counts. Note that this forces a trim of the counts
        """
        min_threshold = max( log(self._epsilon * self._n), 0 )
        if threshold_count is not None:
            assert threshold_count >= min_threshold, "too small threshold"
        else:
            threshold_count = min_threshold
            L.debug(f"Setting threshold to log({self._epsilon}*{self._n}) = {threshold_count}")

        self._trim()
        for item, total in self._count.items():
            # Numbers < threshold_count are sus.
            if total >= threshold_count:
                yield (item, total)

    def most_common(self, n=None, **kwargs):
        """Emulates the same method of collections.Counter
        """
        all_vals = list( self.get_iter(**kwargs) )
        all_vals.sort(key=lambda e: e[1], reverse=True)
        if n is None:
            return all_vals
        else:
            return all_vals[:n]

# Self test if run directly.
if __name__ == "__main__":
    import random
    from collections import Counter

    lcounter = LossyCounter()
    rcounter = Counter() # real counter
    stream = ''
    for i, c in enumerate('abcdefghij', 1):
        stream += c * (2 ** i + random.randint(0,i))

    stream = list(stream)
    print(len(stream))
    random.shuffle(stream)

    for c in stream:
        lcounter.add_count(c)
        # Keep the real counts too.
        rcounter[c] += 1

    for item, count in sorted(lcounter.get_iter(),
                              key=lambda x: x[1], reverse=True):
        print(item, count, rcounter[item])

    print(lcounter._bucket_id)

    # Just to show that .most_common does the thing
    print("Lossy:", lcounter.most_common(8))
    print("Real: ", rcounter.most_common(8))
