#!/usr/bin/env python3

import os, sys, re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging as L
import json
from datetime import datetime, timezone
from pprint import pprint, pformat

from illuminatus import ragic
from illuminatus.aggregator import aggregator

def main(args):

    try:
        if args.json_file:
            with open(args.json_file) as fh:
                run = json.load(fh)

                if run['Flowcell ID'] != args.flowcell_id:
                    exit(f"JSON {args.json_file} has flowcell {run['Flowcell ID']},"
                         f" not {args.flowcell_id}")
        else:

            run = ragic.get_run(args.flowcell_id, add_samples=True)
    except ragic.EmptyResultError as e:
        if args.empty_on_missing:
            # Make life a little easier for the wrapper script
            L.warning(e)
            exit(0)
        else:
            raise

    if args.save:
        jname = f"run_{run['Flowcell ID']}.json"
        L.info(f"Saving out {jname!r}")
        with open(jname, "w") as save_fh:
            json.dump(run, save_fh)

    print(*gen_ss(run), sep="\n")

def mdydate(ragicts=None):
    """Get today's date, or specified date, in silly mm/dd/yyyy format
       wanted by Illumina samplesheet format.
    """
    if ragicts:
        # Ragic dates always look like "2024/10/18 10:17:26" in UTC,
        # regardless of the format and use of localtime on the form design.

        # Parsing a time string known to be UTC in Python is easy but badly documented!
        thedate = datetime.strptime(ragicts,
                                    "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone()
    else:
        # Just print the local current date
        thedate = datetime.now()

    return thedate.strftime("%m/%d/%Y")

def gen_ss(run):
    """Turn that thing into a sample sheet let's gooooo!

       The sample sheet should be identical each time, unless Ragic is changed.
       This means no putting the date of generation into the Date field.
    """
    #return([pformat(run)])

    res = aggregator(ofs=",")

    # Header
    res( "[Header]" )
    res( "IEMFileVersion", "4" )
    res( "Investigator Name", run['Investigator'] )
    res( "Experiment Name", run['Experiment'] )
    res( "Date", mdydate(run['Last Update']) )
    res( "Workflow", "GenerateFASTQ" )
    res( "Application", "FASTQ Only" )
    #res( "Assay", "TruSeq DNA" )
    res( "Chemistry", run['Chemistry'])

    # Read lengths
    res()
    res( "[Reads]" )
    res( run['R1 Cycles'] )
    res( run['R2 Cycles'] )

    # Settings
    res()
    res( "[Settings]" )
    # Nothing here just now.

    # My special bcl2fastq stuff
    res()
    res( "[bcl2fastq]" )
    res( *( ["#index_revcomp"] + [run[f'Lane {n} index revcomp'] for n in "1234"] ) )

    # There may be a neater way to do this but the lanes correspond to the subtables,
    # and I think I can just assume the keys are in order, or else maybe I order on
    # '_header_Y'.
    lane_keys = sorted([k for k in run if k.startswith("_subtable_")])

    res()
    res( "[Data]" )
    res( "Lane", "Sample_ID", "Sample_Name", "Sample_Plate", "Sample_Well",
         "Sample_Project", "I5_Index_ID", "index", "I7_Index_ID", "index2",
         "Description" )
    for lane_idx, lane_key in enumerate(lane_keys):
        for run_elem in tabulate_lane( lane_num = lane_idx + 1,
                                       lane = run[lane_key],
                                       samples_dict = run['Samples__dict'],
                                       fcid = run['Flowcell ID'] ):
            res(run_elem)

    return res

def tabulate_lane(lane_num, lane, samples_dict, fcid):
    """lane_num is the lane number (lane_idx+1)
       lane is a subtable dict from the Ragic record
    """
    res = aggregator(ofs=",")

    # The items are keyed by unpadded integers-as-strings, so I need to do
    # a special numerical sort.
    # FIXME - likely I should sort by library name, regardless of the order
    # in the sub-table
    run_elem_keys = sorted(lane, key=lambda k: int(k))

    for k in run_elem_keys:
        rel = lane[k]
        proj = rel['Library'][0:5]
        pool = rel['Pool'] or 'NoPool'

        # Find the indexes. Index2 might be empty.
        sample_dict = samples_dict[rel['Library']]
        index1 = sample_dict['Index1']
        index2 = sample_dict['Index2']

        res( lane_num,
             f"{pool}__{rel['Library']}",
             "", # Sample_Name
             fcid,
             "", # Sample_Well
             proj, # Sample_Project
             f"{proj}-{index1}",
             index1,
             f"{proj}-{index2}",
             index2,
             rel['Pool'], # May be blank if no pool
        )

    return res

def parse_args(*args):
    description = """This script builds an Illumina sample sheet from info in the Ragic.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("-f", "--flowcell_id", required=True,
                            help="The flowcell ID to look up.")
    argparser.add_argument("-j", "--json_file",
                            help="Load directly from JSON, skipping Ragic query.")
    argparser.add_argument("--save", action="store_true",
                            help="Save out the JSON from Ragic as run_{FCID}.json")
    argparser.add_argument("--empty_on_missing", action="store_true",
                            help="Return an empty file, rather than an error, of not Ragic"
                                 " record is found")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    _args = parse_args()
    L.basicConfig(level=L.INFO, stream=sys.stderr)
    main(_args)
