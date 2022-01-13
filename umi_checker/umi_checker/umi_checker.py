#!/usr/bin/env python3

"""UMI checker with approximate counting.
   First scan the input fastq(.gz) file and approx-count the sequences.
   Then we'll do some plotting.
"""

import os, sys, re
import collections
from math import sqrt
from statistics import stdev, pstdev, variance, mean
import gzip
import logging as L
from pprint import pprint

from .lossy_counting import LossyCounter

class NormalCounter(collections.Counter):
    """Just a normal Counter with an extra method to make it compatible with
       LossyCounter
    """
    def add_count(self, item):
        self[item] += 1
        try:
            self._n += 1
        except AttributeError:
            self._n = 1

    def get_n(self):
        """Note this only returns the count of things added via .add_count()
        """
        return vars(self).get("_n", 0)

def main(args):

    if args.debug:
        L.basicConfig(format='{levelname:.1s}: {message:s}', level=L.DEBUG, style='{')
    else:
        L.basicConfig(format='{message:s}', level=L.INFO, style='{')

    fqfile, = args.fqfile

    with gzip.open(fqfile, mode="rb") as fh:
        counts_obj = get_counts(fh, exact = args.exact,
                                    istart = args.offset or 0,
                                    iend = args.length + (args.offset or 0) if args.length else -1 )

    top_hits = counts_obj.most_common(100)
    #pprint(top_hits)
    #pprint(counts_obj.get_n())

    # Noice. Now what I want is to calculate a running CoV over the top_hits, and then make some fancy
    # plot overlaying the CoV with the histogram. Summon Seaborn!
    top_counts = [ h[1] for h in top_hits ]
    for n, h in enumerate(top_hits):
        umi_seq, count = h
        umi_seq = umi_seq.decode("utf-8")
        running_cov = cov(top_counts[:n+1])

        running_stdev = pstdev(top_counts[:n+1]) if n else 0.0

        print(f"('{umi_seq}', {count}, {running_cov}, {running_stdev}),")

    print(f"Total unique sequences: {len(list(counts_obj.most_common()))}")
    print(f"Estimated number of UMIs: {estimate_umi_count(counts_obj)}")

def estimate_umi_count(counts_obj, window=0):
    """Apply my silly formula to estimate the UMI count based
       on a counts_obj.
       Note that for lossy counts we never seem more than ~70 000 sequences
       so I definitely need to take that into account when interpreting the
       result (of course the real max depends on the lossy counter config).
    """
    window_left = window
    umi_count = 0

    # Variables for doing cumulative stdev
    tally_sum = 0
    tally_sumsq = 0
    tally_n = 0

    for seq, tally in counts_obj.most_common():

        # We want a cumulative standard deviation, rather than calculating the whole list
        # each time. See https://rosettacode.org/wiki/Cumulative_standard_deviation#Python:_Using_a_class_instance
        tally_n += 1
        tally_sum += tally
        tally_sumsq += tally ** 2
        running_stdev = sqrt(tally_sumsq/tally_n - (tally_sum/tally_n) ** 2)

        if (2 * tally) < running_stdev:
            if window_left:
                window_left -= 1
            else:
                # We aren't looking ahead any more
                return umi_count
        else:
            umi_count = tally_n
            window_left = window

    # If we got here we run out of counts so all the sequences are UMIs
    return umi_count

def cov(counts_list):
    """Standard CoV calculation taken from grab_bcl2fastq_stats.py
    """
    if len(counts_list) < 2:
        # Deviation is zero by definition
        return 0.0

    return stdev(counts_list) / mean(counts_list)

def get_counts(fh, exact=False, istart=0, iend=-1, min_len_umi=3):

    # Lossy counter with epsilon=5e-7 keeps the memory usage to ~100MB even if the file is gigabytes
    # in size. May need a smaller value for long UMIs in large files.
    mycounter = NormalCounter() if exact else LossyCounter(epsilon=5e-7)

    # We expect all the UMI sequences to be the same length, whatever that may be.
    umi_lens = set()

    # The usual, take every fourth line
    for n, l in enumerate(fh):
        #Extract seq
        if n % 4 == 1:
            umi = l[istart:iend].rstrip(b"\n")
            if len(umi) not in umi_lens:
                if umi_lens:
                    # Warn about seeing sequences of different lengths.
                    L.warning(f"UMI length was {len(umi)}; we previously saw {umi_lens}")
                if len(umi) < min_len_umi:
                    L.warning(f"Ignoring short sequence {umi} of length {len(umi)}")

                umi_lens.add(len(umi))

            if len(umi) >= min_len_umi:
                mycounter.add_count(umi)

    return mycounter


