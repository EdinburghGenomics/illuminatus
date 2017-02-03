#!/usr/bin/env python3

import os
from argparse import ArgumentParser

from illuminatus.LIMSQuery import get_project_names

def parse_args():
    description = """Simple client for the LIMS query code in illuminatus/LIMSQuery.py
    """
    argparser = ArgumentParser(description=description)
    argparser.add_argument("-l", nargs='+',
                            help="Look up one or more projects by ID.")

    return argparser.parse_args()

def main(args):

    if args.l:
        for proj, name in zip(args.l, get_project_names(*args.l)):
            print("%s = %s" % (proj, name))


if __name__ == '__main__':
    main(parse_args())
