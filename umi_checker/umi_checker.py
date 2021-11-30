#!/usr/bin/env python3

"""UMI checker with approximate counting.
   First scan the input fastq(.gz) file and approx-count the sequences.
   Then we'll do some plotting.
"""

import os, sys, re
import collections
from statistics import stdev, mean
import gzip
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pprint

from lossy_counting import LossyCounter

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

    top_hits = counts_obj.most_common(30)
    pprint(top_hits)
    pprint(counts_obj.get_n())

    # Noice. Now what I want is to calculate a running CoV over the top_hits, and then make some fancy
    # plot overlaying the CoV with the histogram. Summon Seaborn!

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


def parse_args():
    a = ArgumentParser( description = "UMI checking with lossy counting",
                        formatter_class = ArgumentDefaultsHelpFormatter )

    a.add_argument("--exact", action="store_true",
                   help="Use an exact counter, not a lossy one")
    a.add_argument("--offset", type=int,
                   help="Take the UMI from this base (counting from 0)")
    a.add_argument("--length", type=int,
                   help="Length of the UMI, if not the whole sequence")
    a.add_argument("fqfile", nargs=1,
                   help="File of sequences to scan")

    a.add_argument("--debug", "--verbose", action="store_true",
                   help="Show debugging infos")

    return a.parse_args()

if __name__ == "__main__":
    main(parse_args())
