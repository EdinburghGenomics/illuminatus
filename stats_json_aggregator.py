#!/usr/bin/env python3

""" There are already a few scripts that read Stats.json. Information that
    is extracted per-lane should be handled by the multiqc module.
    This will combine stats from across all/multiple lanes for the overview report.
"""
#import os, sys, re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import json
from statistics import mean, stdev
from illuminatus.FixedOrderedDict import FixedOrderedDict
from illuminatus.YAMLOrdered import yaml
from illuminatus.Formatters import rat

def get_data_container():
    return FixedOrderedDict([
        "Number of Indexes",
        "Total Reads Raw",
        "Assigned Reads",
        "Unassigned Reads PF",
        "Fraction PF",
        "Fraction Assigned",
        "Fraction Assigned Raw",
        "Mean Reads Per Sample",
        "Barcode Balance",
    ], allow_overwrite = True)


def main(args):

    all_stats = dict()
    all_tots = dict()

    # Go through all the JSON
    for stats_file in args.json:
        with open(stats_file) as fh: stats_json = json.load(fh)

        # Add the conversion stats per lane
        for cr_per_lane in stats_json['ConversionResults']:
            ln = cr_per_lane["LaneNumber"]
            assert ln not in all_stats, "Lane {} seen already.".format(ln)

            all_stats[ln] = cr_per_lane["DemuxResults"]

            all_tots[ln] = dict(totraw=0, totpf=0)
            all_tots[ln]['totraw'] = cr_per_lane["TotalClustersRaw"]
            all_tots[ln]['totpf'] = cr_per_lane["TotalClustersPF"]

    #Now calculate the barcode balance the same way as in grab_bcl2fastq_stats.py
    all_stats_out = dict()
    for lane, dres in all_stats.items():

        s = get_data_container()

        num_indices = len([d for d in dres if "IndexMetrics" in d])
        s['Number of Indexes'] = num_indices

        if num_indices <= 1:
            # No barcode balance to report.
            assert len(dres) == 1, "If there are zero or one indexes I expect exactly one sample, but see {}.".format(len(dres))
        else:
            s['Barcode Balance'] = rat( stdev(d["NumberReads"] for d in dres),
                                        mean(d["NumberReads"] for d in dres) )

        sum_assigned = sum(d["NumberReads"] for d in dres)
        s['Assigned Reads'] = sum_assigned
        s['Unassigned Reads PF'] = all_tots[lane]['totpf'] - sum_assigned

        # I supect these two are meaningless for the Novaseq since for a failed read it literally does
        # not have the barcode data and so will never assign it.
        # In which case...
        #s['Assigned Reads Raw'] = s['Assigned Reads PF']
        #s['Unassigned Reads Raw'] = all_tots[lane]['totraw'] - sum_assigned
        s['Total Reads Raw'] = all_tots[lane]['totraw']

        s["Fraction PF"] = rat( all_tots[lane]['totpf'], all_tots[lane]['totraw'] )
        # This matches the existing behaviour.
        s["Fraction Assigned"] = rat(sum_assigned, all_tots[lane]['totraw'])

        s['Mean Reads Per Sample'] = mean(d["NumberReads"] for d in dres)

        all_stats_out[lane] = s.to_dict()

    print(yaml.safe_dump(all_stats_out, default_flow_style=False))


def parse_args(*args):

    desc = "Extract some info from multiple Stats.json. See also summarize_by_project.py"

    parser = ArgumentParser( description = desc,
                             formatter_class = ArgumentDefaultsHelpFormatter )

    parser.add_argument("json", type=str, nargs='+',
                        help="Stats to be digested.")

    return parser.parse_args(*args)

if __name__=="__main__":
    main(parse_args())
