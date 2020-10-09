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
    num_cycles_1 = int(run_info_root.find("Run/Reads/Read[@Number='1']").get('NumCycles'))
    if num_cycles_1 <= (READ_LENGTH + START_POS):
        START_POS = 0
        if not num_cycles_1 > READ_LENGTH:
            # See if we can use read 3?
            try:
                num_cycles_3 = int(run_info_root.find("Run/Reads/Read[@Number='3']").get('NumCycles'))
                if num_cycles_3 > READ_LENGTH:
                    num_cycles_2 = int(run_info_root.find("Run/Reads/Read[@Number='2']").get('NumCycles'))
                    START_POS = num_cycles_1 + num_cycles_2
                else:
                    # Drop to exception handling
                    raise Exception("No dice")
            except Exception:
                # We can't process this run
                print("Cannot process run with {} cycles in read 1.".format(num_cycles_1), file=sys.stderr)
                LANES_TO_SAMPLE = []
    END_POS = READ_LENGTH + START_POS

print("Sampling from {} to {} on lanes {}".format( START_POS, END_POS, list(LANES_TO_SAMPLE) ))
