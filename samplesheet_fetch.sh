#!/bin/bash

# This script will fetch a new SampleSheet for the current run. It must
# be run in the folder where the sequencer data has been written. For testing, try:
# $ ( PATH="$PWD:$PATH" ; cd ~/test_seqdata/170703_D00261_0418_ACB6HTANXX/ ; samplesheet_fetch.sh )
set -e ; set -u

# Support a SampleSheet postprocessor hook. This must take one argument,
# the file to be read, and print to stdout.
SSPP_HOOK="${SSPP_HOOK:-}"

if [ -z "${FLOWCELLID:-}" ] ; then
    #Try to determine flowcell ID by asking RunInfo.py
    FLOWCELLID=`RunInfo.py | grep '^Flowcell:' | cut -f2 -d' '`
fi

if [ -z "${FLOWCELLID:-}" ] ; then
    echo "No FLOWCELLID was provided, and obtaining one from RunInfo.py failed."
    exit 1
fi

# Zerothly, remove any dangling symlink
if [ ! -e SampleSheet.csv ] ; then
    rm -f SampleSheet.csv
fi

# Firstly, SampleSheet.csv.0 needs to contain the original file from the
# sequencer. It is technically possible to run the machine with no sample
# sheet. In this case, the script will make an empty file.
if [ ! -e SampleSheet.csv.0 ] && [ ! -L SampleSheet.csv ] ; then
    if mv SampleSheet.csv SampleSheet.csv.0 ; then
        echo "SampleSheet.csv renamed as SampleSheet.csv.0"
    else
        touch SampleSheet.csv.0
        echo "SampleSheet.csv.0 created as empty file"
    fi
fi

# Make link only if SampleSheet.csv was missing.
ln -s SampleSheet.csv.0 SampleSheet.csv 2>/dev/null || true

# At this point we may expect that SampleSheet.csv is a symlink. Sanity check.
if [ ! -L SampleSheet.csv ] ; then
    echo "Sanity check failed - SampleSheet.csv is not a symlink"
    #If the link was changed into a file, try to undo the change
    if [ -e SampleSheet.csv ] ; then
        for candidate_ss in SampleSheet.csv.* ; do
            if diff -q "$candidate_ss" SampleSheet.csv ; then
                #Keep going - if several match the latest will end up linked.
                echo "But it is identical to $candidate_ss, so linking it to that."
                ln -sf "$candidate_ss" SampleSheet.csv
            fi
        done
    fi
    # If it's still not a symlink, give up.
    [ -L SampleSheet.csv ] || exit 1
fi

# Support OVERRIDE with local SampleSheet
if [ -e SampleSheet.csv.OVERRIDE ] ; then
    echo "Giving priority to ./SampleSheet.csv.OVERRIDE"

    ln -sf SampleSheet.csv.OVERRIDE SampleSheet.csv
    echo "SampleSheet.csv for ${FLOWCELLID} is now linked to new SampleSheet.csv.OVERRIDE"
    exit 0
fi

# Find a candidate sample sheet, from the files on /ifs/clarity (or wherever)

# Read the Genologics configuration with the same priorities as the LIMSQuery.py code.
# This is a bit hacky, but it is effective.
eval `grep -h '^FS_ROOT=' /etc/genologics.conf genologics.cfg genologics.conf ~/.genologicsrc ${GENOLOGICSRC:-/dev/null} 2>/dev/null`
test -d "$FS_ROOT"

# The latest one that matches the flowvell ID is the one we want.
# Or do we want to sort on some other criterion?
candidate_ss=`find "$FS_ROOT/samplesheets_bcl2fastq_format" -name "*_${FLOWCELLID}.csv" -print0 | xargs -r0 ls -tr | tail -n 1`

if [ ! -e "$candidate_ss" ] ; then
    echo "No candidate replacement samplesheet for ${FLOWCELLID} under $FS_ROOT/samplesheets_bcl2fastq_format"
elif [ -z "$SSPP_HOOK" ] && diff -q "$candidate_ss" SampleSheet.csv ; then
    #Nothing to do.
    echo "SampleSheet.csv for ${FLOWCELLID} is already up-to-date"
else
    #Using noclobber to attempt writing to files until we find an unused name
    set -o noclobber
    counter=1
    while ! true > "SampleSheet.csv.$counter" ; do
        counter=$(( $counter + 1 ))

        #Just in case there was some other write error
        test $counter -lt 1000
    done
    "${SSPP_HOOK:-cat}" "$candidate_ss" >> "SampleSheet.csv.$counter"

    if [ -n "$SSPP_HOOK" ] ; then
        # In this case we need to check for differences post-filtering.
        if diff -q "SampleSheet.csv.$counter" SampleSheet.csv ; then
            echo "SampleSheet.csv for ${FLOWCELLID} is already up-to-date (after filtering)."
            rm -f "SampleSheet.csv.$counter"
            exit 0
        fi
    fi

    ln -sf "SampleSheet.csv.$counter" SampleSheet.csv #Should be safe - we checked it was only a link
    echo "SampleSheet.csv for ${FLOWCELLID} is now linked to new SampleSheet.csv.$counter"
fi

