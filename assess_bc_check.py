#!/usr/bin/env python3

"""Script to scan the results of the bcl2fastq_bc_check rule in Snakefile.read1qc
   and note any problems.
   The idea is that any message printed by this script is put into an alert mail
   by the driver.sh.
   If no problems are found then the script prints no output, and then no alert will
   be sent.
"""
import os, sys, re
import json
from collections import Counter
from pprint import pprint, pformat

# Debug output can be activated by the test framework
import logging as L
L.basicConfig(level = L.WARNING)

def main(list_of_inputs):
    res = []

    # The list_of_inputs may be the Stats.json files or else just the directories.
    # Convert them anyway.
    stats_json = set()
    for i in list_of_inputs:
        if os.path.exists(i + '/Stats/Stats.json'):
            stats_json.add(i + '/Stats/Stats.json')
        elif i.endswith('.json'):
            stats_json.add(i)
        else:
            exit("Invalid input: {} needs to be dir with Stats/Stats.json or a Stats.json file".format(i))

    if not stats_json:
        exit("You need to supply one or more Stats.json files to be assessed")

    # Load the infos
    all_infos = dict()
    for s in stats_json:
        ls = load_stats(s)
        all_infos[ls['lane']] = ls

    # Now pass judgement on them
    for lane, info in sorted(all_infos.items()):
        diagnosis = diagnose(info)
        if res and diagnosis:
            # Spacer line
            res.append('')
        if diagnosis:
            res.append("Problem in lane {}:".format(lane))
            res.extend(diagnosis)

    return res

def diagnose(lane_info):
    """Diagnose 1 set of conversion results relating to one lane.
       Returns a list of lines or None.
    """
    cr = lane_info['cr']

    if cr["TotalClustersPF"] == 0:
        # No good reads, so we can't assess the barcodes.
        return ["No clusters passing filter were found on the sample tile."]

    if not "Undetermined" in cr:
        # We assume this is a barcode-less run. So we're good.
        return

    num_unassigned = cr["Undetermined"]["NumberReads"]

    # We need to tot up the number assigned to each project and see if any total is less than
    # num_unassigned. As usual assume the first 5 chars of the SampleId are the project.
    num_by_project = Counter()
    for dr in cr["DemuxResults"]:
        proj = dr["SampleId"][:5]
        num_by_project[proj] += dr["NumberReads"]
    L.debug("Reads by project: " + str(num_by_project))

    # We only want ones where the count is < Undetermined
    num_by_project = { k: v for k, v in num_by_project.items() if v < num_unassigned }

    if num_by_project:
        # Probably there is only one but there could be more if we start mixing lanes again
        res = [ "Project {} has only {} total reads, compared to {} unassigned.".format(
                         k,          v,                         num_unassigned)
                for k, v in num_by_project.items() ]
        res.append('')

        if lane_info['opts']:
            mismatch = lane_info['opts'].get('--barcode-mismatches', "[not_set]")
            res.append("Barcode mismatch level was set to {} for this lane.".format(mismatch))
            res.append('')

        if lane_info['unass']:
            res.append("Top unassigned codes. See the HTML report for the full list...")
            res.append('---')
            res.extend(lane_info['unass'][:10])
            res.append('---')
        else:
            res.append("ERROR - Unable to load unassigned list from unassigned_table.txt")

        return res

    # Any other problems I should be diagnosing? Nope? OK cool.
    return

def load_stats(stats_info):
    """Load a single stats_info file and try to also load the corresponding
       ../bcl2fastq.opts, but if this is missing it's not a problem.
    """
    res = dict()

    with open(stats_info) as jfh:
        stats_json= json.load(jfh)

    # Get the lane from the JSON
    try:
        res['cr'], = stats_json['ConversionResults']
    except ValueError:
        # In general it's valid for a Stats.json file to relate to multiple lanes, but in
        # Illuminatus we only ever demux one lane at a time, so at present this script only
        # deals with the single-lane case.
        raise RuntimeError("File {} does not contain info on a single lane as expected.".format(stats_info))

    # This should be an int already
    res['lane'] = int(res['cr']['LaneNumber'])

    # See if we can find the bcl2fastq.opts file and convert it to a dict
    opts_file = os.path.join( os.path.dirname(stats_info), '../bcl2fastq.opts' )
    try:
        with open(opts_file) as fh:
            res['opts'] = dict()
            for l in fh:
                res['opts'].update([re.split(r'[= \t]+', l.strip())])
    except FileNotFoundError:
        res['opts'] = None

    # See if there is an unassigned_table.txt to look at. Note this file only contains
    # info that can be got from the Stats.json but we already have a script to check
    # chack for revcomps so no need to repeat ourselves.
    unass_file = os.path.join( os.path.dirname(stats_info), '../unassigned_table.txt' )
    try:
        with open(unass_file) as fh:
            res['unass'] = [ l.rstrip('\n') for l in fh ]
    except FileNotFoundError:
        res['unass'] = None

    return res

if __name__ == '__main__':
    for msg_line in main(sys.argv[1:]):
        print(msg_line)
