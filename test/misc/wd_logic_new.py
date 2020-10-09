#!/usr/bin/env python3

# This is a tester for the logic that works out WD cycles to sample. Old logic...
import sys
import xml.etree.ElementTree as ET

RUNDIR = sys.argv[1]
READ_LENGTH = 50
START_POS = 20

run_info_root = ET.parse(RUNDIR + "/RunInfo.xml").getroot()

LAST_LANE = '0' ; LAST_TILE = FIRST_TILE = '0000'
try:
    LAST_LANE, LAST_TILE = max(te.text for te in run_info_root.findall(".//Tiles/Tile")).split('_')
    _, FIRST_TILE = min(te.text for te in run_info_root.findall(".//Tiles/Tile")).split('_')
except ValueError:
    # If there are no tiles we can reasonably assume we're on a non-patterned
    # Flowell (MiSeq or 2500). In this case, do nothing., which we can achieve by
    # inserting a no-op rule if LAST_LANE == 0 - see wd_main.
    pass

# Lanes to sample is now variable since the arrival of Novaseq, so get it from
# RunInfo.xml...
LANES_TO_SAMPLE = range(1, int(LAST_LANE) + 1)

if LANES_TO_SAMPLE:
    # Find the first read that has >READ_LENGTH cycles. Normally read1 will do.
    # If not using read1, always set START_POS to the first cycle of that read.
    all_read_lens = [ int(r.get('NumCycles')) for r in
                      sorted( run_info_root.findall("Run/Reads/Read"),
                              key = lambda r: int(r.get("Number")) ) ]
    if max(all_read_lens) > READ_LENGTH:
        read_to_sample = [ n for n, l in enumerate(all_read_lens) if l > READ_LENGTH ][0]

        # Is it OK to start at START_POS or do we go from 0?
        if not (read_to_sample == 0 and all_read_lens[read_to_sample] > (READ_LENGTH + START_POS)):
            START_POS = 0

        # Now we have the relative START_POS, calculate the absolute START_POS
        START_POS += sum( all_read_lens[:read_to_sample] )
    else:
        # We can't process this run
        print("Cannot process run with short read lengths {}.".format(all_read_lens), file=sys.stderr)
        LANES_TO_SAMPLE = []

    END_POS = READ_LENGTH + START_POS

print("Sampling from {} to {} on lanes {}".format( START_POS, END_POS, list(LANES_TO_SAMPLE) ))
