#!/usr/bin/env python3

# This is not used in the actual pipeline but useful for testing.

import os
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from illuminatus import get_project_names

def parse_args():
    description = """Simple client for the get_project_names query.
    """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )

    argparser.add_argument("-l", nargs='+',
                            help="Look up one or more projects by ID.")

    return argparser.parse_args()

def main(args):

    if args.l:
        for proj, name in zip(args.l, get_project_names(*args.l)):
            print(f"{proj} = {name}")


if __name__ == '__main__':
    main(parse_args())
