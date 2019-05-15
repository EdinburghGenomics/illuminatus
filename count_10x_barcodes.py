#!/usr/bin/env python3
import sys, os
import json
from glob import glob

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

TX_CODES = os.path.dirname(__file__) + '/10x_barcodes/*.txt'

""" Given a demultiplexed run, how many 10x barcodes were present.
"""

def main(args):

    all_10x = set( c['Sequence'] for c in load_10x_codes() )
    all_found = list()

    for stats_file in args.json:

        codes_found = set()

        with open(stats_file) as fh: stats_json = json.load(fh)

        for cr in stats_json['ConversionResults']:
            for dr in cr['DemuxResults']:
                for im in dr.get('IndexMetrics',[]):
                    idx = im['IndexSequence']

                    if idx in all_10x:
                        codes_found.add(idx)

        all_found.append(codes_found)

    if args.verbose:
        for jf, cf in zip(args.json, all_found):
            print("Codes found in {} ({}):".format(jf, len(cf)))
            print(" {!r}".format(sorted(cf)))
        print("Max found: {}".format(max(len(cf) for cf in all_found)))

    # For scripting, return true if this is a 10x run.
    exit(1 if max(len(cf) for cf in all_found) < 4 else 0)

def load_10x_codes():
    """Return a list of dicts
    """
    res = []

    for cf in glob(TX_CODES):
        with open(cf) as cfh:
            head = next(cfh).split()
            for l in cfh:
                res.append(dict(zip(head, l.split())))

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
    main(parse_args())
