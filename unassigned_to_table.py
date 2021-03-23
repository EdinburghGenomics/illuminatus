#!/usr/bin/env python3
import os, sys, re
import json
import logging as L

# Take the Stats.json and produce a basic text table of the unassigned
# barcodes. This code was originally in multiqc_edgen/modules/edgen_unassigned/edgen_unassigned.py
# but it got a little complex so I'm breaking it out into the pipeline proper.

# Note that if there are no barcodes in the run or the Stats.json contains multiple lanes the
# output will be empty and a wraning will be logged on STDERR.

def format_lines(json_data, maxlines=None, commentor=lambda *ub: ''):
    """Given the content of a Stats.json file as a Python object,
       return a list of lines that we can embed into the MultiQC report.
    """
    ub = json_data.get("UnknownBarcodes")

    if not ub:
        L.warning("No unknown barcodes in this JSON data.")
        return []
    if len(ub) != 1:
        # TODO - check I got this right
        L.warning("JSON data contains info for more than one lane.")
        return []

    # There is one lane. Good.
    ub_codes = ub[0]["Barcodes"]

    # Now we have a dict. In the original files the list is sorted by count but this will
    # be lost, so re-sort. Also we can lose the overspill.
    ub_sorted = sorted(ub_codes.items(), key=lambda i: int(i[1]), reverse=True)[:maxlines]

    # Add comment to the end of each line. This incolves converting the tuples to lists.
    ub_sorted = [ list(ub) + [commentor(*ub)] for ub in ub_sorted ]

    # Get the appropriate column widths. Note that 0 is an illegal width.
    colwidth = [0,0,0]
    for n in range(len(colwidth)):
        colwidth[n] = max(len(str(i[n])) for i in ub_sorted) or 1

    line_template = '  '.join(["{:{}}"] * len(colwidth))
    L.debug(line_template)
    L.debug([x for z in zip(ub_sorted[0],colwidth) for x in z])
    return [ line_template.format(*[x for z in zip(i,colwidth) for x in z]).rstrip()
             for i in ub_sorted ]

def make_revcomp_commentor(sdict):
    """Return a commentor function that looks for likely reverse-complement
       issues. Note we don't look for reversed or swapped codes or anything
       other than revcomp.
    """
    # Sanitize all the names in sdict, while also ensuring that changes to
    # the original dict cannot alter the function output.
    newdict = { k: v.split('__')[-1] for k, v in sdict.items() }

    # We only care about the barcode not the count, so define the fuction like so:
    def comm_func(bc, *_):

        # Simple case
        if bc in newdict:
            return "is " + newdict[bc]

        # The bc may or may not have a '+'
        bc_split = bc.split('+')

        if len(bc_split) > 2:
            # I could make this work for any number of indices but it would just
            # make the code ugly and would never do anything useful.
            return ""
        elif len(bc_split) == 1:
            if revcomp(bc) in newdict:
                return "revcomp of " + newdict[revcomp(bc)]
            else:
                # No match, no message
                return ""
        else:
            # Here we need a list of possible matches - see the unit tests
            poss_matches = [ ('idx1',
                              newdict.get(revcomp(bc_split[0]) + "+" + bc_split[1])),
                             ('idx2',
                              newdict.get(bc_split[0] + "+" + revcomp(bc_split[1]))),
                             ('idx1+2',
                              newdict.get(revcomp(bc_split[0]) + "+" + revcomp(bc_split[1]))) ]
            # String-ify. This works for the no-match case too
            return "; ".join([ "revcomp {} of {}".format(*pm) for pm in poss_matches
                               if pm[1] ])

    return comm_func

def revcomp(seq, rep_table=str.maketrans('ATCGatcg', 'TAGCtagc')):
    """The classic!
    """
    return seq.translate(rep_table)[::-1]

def get_samples_list(json_data):
    """This is implemented elsewhere, but I'll re-implement it here. List
       the samples from the JSON, in the form of as dict of {barcode: sample}
    """
    con_res = json_data.get('ConversionResults')

    # We expect one of these, and then there should be a DemuxResults list that is one
    # per sample.
    if not con_res or len(con_res) != 1:
        L.warning("Cannot get table of sample barcodes from JSON data")
        return {}

    dem_res = con_res[0]["DemuxResults"]
    if not dem_res:
        L.warning("Table of sample barcodes from JSON data is empty")

    res = {}
    for sample in dem_res:
        sample_name = sample.get("SampleId") or sample.get("SampleName") or 'unnamed'

        # In Stats.json a sample may have multiple index sequences. Not sure if bcl2fastq actually supports
        # this but we have a list in any case.
        for sample_index in sample.get("IndexMetrics", []):
            res[sample_index["IndexSequence"]] = sample_name

    return res

def main(args):
    if not len(args) == 1:
        exit("Usage: unassigned_to_table.py <Stats.json>")

    with open(args[0]) as sfh:
        json_data = json.load(sfh)

    # Commentor needs to know the expected samples
    expected_samples = get_samples_list(json_data)
    commentor = make_revcomp_commentor(expected_samples)

    out_lines = format_lines(json_data, maxlines=200, commentor=commentor)

    for l in out_lines:
        print(l)

if __name__ == '__main__':
    # Logging in use for the benefit of unit tests
    L.basicConfig(format='{message:s}', level=L.INFO, style='{')
    main(sys.argv[1:])
