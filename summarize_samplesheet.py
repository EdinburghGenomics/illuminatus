#!/usr/bin/env python3
import sys
from argparse import ArgumentParser

# TODO - we may need to digest the info into YAML first in order to avoid
# parsing the data twice - once to make a text message for RT and again to
# get info for MultiQC.

def parse_args():
    description = """This script is part of the Illuminatus pipeline.
It makes the Samplesheet report that was previously handled by
wiki-communication/bin/upload_run_info_on_wiki.py, by parsing the SampleSheet.csv
and RunInfo.xml in the current directory and by asking the LIMS for proper project names.

In the initial incarnation, it just dumps out the file.
"""
    argparser = ArgumentParser(description=description)
    argparser.add_argument("--project_names",
                            help="Supply a comma-separated list of project names." +
                                 "If you do this, the LIMS will not be queried.")

    return argparser.parse_args()

def main(args):

    print("Machine: {machine}")
    print("Run type: {run_type}")
    print("Read length: {read_len}")
    print()

    print("Samplesheet report at {date}:")
    try:
        with open("SampleSheet.csv") as ss_fh:
            print(ss_fh.read(), end='')
    except FileNotFoundError as e:
        print(e)

# FIXME - use the real version from illuminatus.LIMSQuery instead.
def project_real_name(proj_id_list, name_list=None):
    """Resolves a list of project IDs to a name and URL
    """
    res = dict()
    if name_list:
        #Resolve without going to the LIMS
        for p in proj_id_list:
            name_match = [ n for n in name_list if n.startswith(p) ]
            if len(name_match) == 1:
                res[p] = dict( name = name_match[0],
                               url  = "http://foo.example.com/" + name_match[0] )
            else:
                res[p] = dict( name = p + "_UNKNOWN" )
    else:
        #TODO
        lookup_in_lims(proj_id_list, blah)

    return res

if __name__ == "__main__":
    main(parse_args())
