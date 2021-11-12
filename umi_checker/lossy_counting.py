"""Lossy Counting in pure Python

   https://gist.github.com/giwa/bce63f3e2bd493167d92

   Updated for Python3
"""

from collections import defaultdict

class LossyCounter(object):
    'Implemendation of Lossy Counting'

    def __init__(self, epsilon=5e-4):
        self._n = 0
        self._count = defaultdict(int)
        self._bucket_id = {}
        self._epsilon = epsilon
        self._current_bucket_id = 1

    def get_count(self, item):
        """Return the number of the item
        """
        return self._count[item]

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

    def get_iter(self, threshold_count=0):
        """Extract the counts. Note that this forces a trim of the counts
        """
        if threshold_count:
            assert threshold_count > self._epsilon * self._n, "too small threshold"

        self._trim()
        for item, total in self._count.items():
            total_and_bucket = total + self._bucket_id[item]
            if total_and_bucket >= threshold_count - self._epsilon * self._n:
                yield (item, total_and_bucket)


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
        rcounter[c] += 1

    for item, count in sorted(lcounter.get_iter(),
                              key=lambda x: x[1], reverse=True):
        print(item, count, rcounter[item])

    print(lcounter._bucket_id)
