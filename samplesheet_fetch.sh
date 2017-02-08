#!/bin/bash

# This script will fetch a new SampleSheet for the current run. It must
# be run in the folder where the sequencer data has been written.
set -e ; set -u

if [ -z "${FLOWCELLID:-}" ] ; then
    #Try to determine flowcell ID by asking RunInfo.py
    FLOWCELLID=`RunInfo.py | grep '^Flowcell:' | cut -f2 -d' '`
fi


# Firstly, SampleSheet.csv.0 needs to contain the original file from the
# sequencer. It is technically possible to run the machine with no sample
# sheet. In this case, the script will make an empty file.
if [ ! -e SampleSheet.csv.0 ] ; then
    if mv SampleSheet.csv SampleSheet.csv.0 ; then
        echo "SampleSheet.csv renamed as SampleSheet.csv.0"
    else
        touch SampleSheet.csv.0
        echo "SampleSheet.csv.0 created as empty file"
    fi
    ln -s SampleSheet.csv.0 SampleSheet.csv
fi

# At this point we may expect that SampleSheet.csv is a symlink. Sanity check.
test -L SampleSheet.csv

# Find a candidate sample sheet, from the files on /ifs/clarity (or wherever)

# Read the Genologics configuration with the same priorities as the LIMSQuery.py code.
# This is a bit hacky, but it is effective.
eval `grep -h '^FS_ROOT=' /etc/genologics.conf genologics.cfg genologics.conf ~/.genologicsrc ${GENOLOGICSRC:-/dev/null} 2>/dev/null`
test -d "$FS_ROOT"

# The latest one that matches the flowvell ID is the one we want.
# Or do we want to sort on some other criterion?
candidate_ss=`find "$FS_ROOT/samplesheets_bcl2fastq_format" -name "*_${FLOWCELLID}.csv" -print0 | xargs -r0 ls -tr | tail -n 1`

if [ ! -e "$candidate_ss" ] ; then
    echo "No candidate replacement samplesheet under $FS_ROOT/samplesheets_bcl2fastq_format"
elif diff -q "$candidate_ss" SampleSheet.csv ; then
    #Nothing to do.
    echo "SampleSheet.csv is already up-to-date"
else
    #Using noclobber to attempt writing to files until we find an unused name
    set noclobber
    counter=1
    while ! cat "$candidate_ss" > "SampleSheet.csv.$counter" ; do
        counter=$(( $counter + 1 ))

        #Just in case there was some other write error
        test $counter -lt 1000
    done

    ln -sf "SampleSheet.csv.$counter" SampleSheet.csv #Should be safe - we checked it was only a link
    echo "SampleSheet.csv is now linked to new SampleSheet.csv.$counter"
fi

