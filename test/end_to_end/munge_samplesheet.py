#!/usr/bin/env python3

# In production, the SampleSheet.csv produced by Clarity should always be the final
# one that goes into bcl2fastq.

# However, some of the older runs we want to test on have the older formats, so
# this script will just bolt the pool name onto the library name for us.

import sys, os, re
import traceback

def main(infile):

    # Slurp and strip
    with open(infile) as ifh:
        lines = [ l.rstrip("\n") for l in ifh ]
        # Keep a fresh copy in case munge_lines raises an exception
        new_lines = lines.copy()

    # Find the '[Data]' line
    try:
        if munge_lines(lines):
            # OK we can use these lines now
            new_lines = lines
    except Exception as e:
        # Just warn (to stderr)
        traceback.print_tb(e.__traceback__)

    for l in new_lines:
        print(l)

def munge_lines(lines):
    """Alter the lines. If in doubt, raise an exception and keep the old version.
       If the file is already right, return False to keep the old one without printing
       an error trace.
    """

    data_line = lines.index('[Data]')

    #Check the header
    if lines[data_line+1].startswith('Sample_ID,Sample_Name,'):
        sn_col = 1
        si_col = 0
    else:
        assert lines[data_line+1].startswith('Lane,Sample_ID,Sample_Name,')
        sn_col = 2
        si_col = 1
    assert lines[data_line+1].endswith(',Description')

    first_line = data_line + 2

    last_line = len(lines) - 1
    # Allow for blank lines on the end
    while ',' not in lines[last_line]:
        last_line -= 1

    # We should see at least one line
    assert last_line >= first_line

    for l in range(first_line, last_line+1):
        split_line = lines[l].split(',')

        if '__' in split_line[si_col]:
            # Already looks right
            return False

        # In the sheets we're dealing with, Sample_Name and Description should be set the same.
        assert split_line[sn_col] == split_line[-1]

        pool = split_line[-1] or 'NoPool'

        # Make the change.
        split_line[si_col] = pool + '__' + split_line[si_col]
        split_line[sn_col] = ''

        lines[l] = ','.join(split_line)

    # Note the processing
    desc_line = lines.index('Description')
    lines[desc_line] = 'Description,Munged for testing by munge_samplesheet.py'

    return True

main(sys.argv[1])
