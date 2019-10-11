#!/usr/bin/env python3
import sys, os
import json
from glob import glob

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

# These files come direct from 10x:
# https://support.10xgenomics.com/single-cell-gene-expression/sequencing/doc/specifications-sample-index-sets-for-single-cell-3
# Note the use of abspath is needed to keep the tests happy.
TX_CODES = os.path.abspath(os.path.dirname(__file__)) + '/10x_barcodes/*.csv'

""" Given a demultiplexed run, how many 10x barcodes were present.
"""

def main(args):

    # Two dicts indexed by filename. One has sets of  10x barcodes. The other has sets to collect
    # barcodes seen in each Stats.json (ie. a dict of dicts of sets).
    all_10x = { f : set(seq for l in lines for seq in l['Sequence'])
                for f, lines in load_10x_codes().items() }
    all_found = { f: dict() for f in all_10x }

    for stats_file in args.json:

        codes_found = { f: set() for f in all_10x }

        with open(stats_file) as fh: stats_json = json.load(fh)

        for cr in stats_json['ConversionResults']:
            for dr in cr['DemuxResults']:
                for im in dr.get('IndexMetrics',[]):
                    idx = im['IndexSequence']

                    for f in all_10x:
                        if idx in all_10x[f]:
                            codes_found[f].add(idx)

        for f in all_10x:
            all_found[f][stats_file] = codes_found[f]

    if args.verbose:
        for stats_file in args.json:
            print("Codes found in {} ({}):".format(stats_file, sum( len(afset[stats_file]) for afset in all_found.values() )))
            for f in all_10x:
                print(" {!r}".format(sorted(all_found[f][stats_file])))
        print("Max found: {}".format(max(len(cf) for af in all_found.values() for cf in af.values())))

    # For scripting, return true if this is (apparently) a 10x run, with at least one
    # JSON file having at least 4 barocdes from a single barcode set.
    return max(len(cf) for af in all_found.values() for cf in af.values()) >= 4

def load_10x_codes():
    """Return a dict of list of dicts
       { 'filename' : [ { Name: '...', Sequence: [...] },
                        { ...line2... },
                        { ...line3... } ],
         ...
       }
    """
    res = dict()

    for cf in glob(TX_CODES):
        with open(cf) as cfh:
            cflines = res[os.path.basename(cf)] = list()
            for l in cfh:
                lparts = l.strip().split(',')
                cflines.append(dict( Name=lparts[0], Sequence=lparts[1:] ))

    return res


def parse_args(*args):

    desc = "Count 10x barcodes in multiple Stats.json."

    parser = ArgumentParser( description = desc,
                             formatter_class = ArgumentDefaultsHelpFormatter )

    parser.add_argument("json", type=str, nargs='+',
                        help="Stats to be digested.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print a report.")

    return parser.parse_args(*args)

if __name__=="__main__":
    exit(0 if main(parse_args()) else 1)
