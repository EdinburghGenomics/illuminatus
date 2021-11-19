#!/usr/bin/env python3

"""UMI checker with approximate counting.
   First scan the input fastq(.gz) file and approx-count the sequences.
   Then we'll do some plotting.
"""

import os, sys, re
import collections
import gzip
import logging as L
from lossy_counting import LossyCounter
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

class NormalCounter(collections.Counter):
    """Just a normal counter with an extra method to make it compatible with
       LossyCounter
    """
    def add_count(self, item):
        self[item] += 1

def main(args):

    L.basicConfig(format='{message:s}', level=L.INFO, style='{')

    fqfile, = args.fqfile

    with gzip.open(fqfile, mode="rb") as fh:
        counts_obj = get_counts(fh, exact = args.exact,
                                    istart = args.offset or 0,
                                    iend = args.length + (args.offset or 0) if args.length else -1 )

    pprint(counts_obj.most_common(30))

def get_counts(fh, exact=False, istart=0, iend=-1):

    if exact:
        counter = NormalCounter()
    else:
        counter = LossyCounter()

    umi_len = None

    # The usual, take every fourth line
    for n, l in enumerate(fh):
        #Extract seq
        if n % 4 == 2:
            umi = l[istart:iend].rstrip(b"\n")
            if not umi_len:
                umi_len = len(umi)
                if umi_len < 3:
                    exit("Sequence length too short")
            else:
                if umi_len != len(l) -1:
                    # Spew warnings
                    L.warning(f"UMI length was {len(l) - 1} expected {umi_len}")

            counter.add_count(umi)

    return counter


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

    return a.parse_args()

if __name__ == "__main__":
    main(parse_args())
