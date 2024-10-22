#!/bin/bash

# This script will generate a new SampleSheet from Ragic for the current run. It must
# be run in the folder where the sequencer data has been written. For testing, try:
# $ cd ~/test_seqdata/170703_D00261_0418_ACB6HTANXX/ ; samplesheet_fetch.sh
#
# Note there is no actual Ragic stuff until way down at line 100. Before then we do a
# ton of sanity chacking on what we already have.
#
set -euo pipefail
shopt -s nullglob

# The $PATH should be set by the driver, but to allow this script to be run standalone:
if ! which RunStatus.py >&/dev/null ; then
    PATH="$(readlink -f $(dirname "$BASH_SOURCE")):$PATH"
fi

# Support a SampleSheet postprocessor hook. This must read the SampleSheet from stdin,
# and print the filtered version to stdout. The full file path will also be set in SSPP_FILE
# if the script need to see that for any reason.
# I'm not really using this in production
# since the samplesheets are now specifically generated for this pipeline.
SSPP_HOOK="${SSPP_HOOK:-cat}"

if [ -z "${FLOWCELLID:-}" ] ; then
    #Try to determine flowcell ID by asking RunStatus.py
    FLOWCELLID=$(RunStatus.py | grep '^Flowcell:' | cut -f2 -d' ') || true
fi

if [ -z "${FLOWCELLID:-}" ] ; then
    echo "No FLOWCELLID was provided, and obtaining one from RunStatus.py failed"
    exit 1
fi

# And also force the FLOWCELLID to upper case, because reasons.
UFLOWCELLID="$(tr a-z A-Z <<<"$FLOWCELLID")"

# Zerothly, remove any dangling symlink
if [ ! -e SampleSheet.csv ] ; then
    rm -f SampleSheet.csv
fi

# List the sample sheet files we have here already
all_sheets=(SampleSheet.csv.[0-9]*)

# SampleSheet.csv.0 needs to contain the original file from the
# sequencer. It is also possible to run the NovaSeq with no sample
# sheet. In that case this script will make SampleSheet.csv.0 as an empty file.
if [ ! -e SampleSheet.csv.0 ] && [ ! -L SampleSheet.csv ] ; then
    if mv SampleSheet.csv SampleSheet.csv.0 ; then
        echo "SampleSheet.csv renamed as SampleSheet.csv.0"
        all_sheets=(SampleSheet.csv.0 ${all_sheets[@]})
    else
        if [ "${#all_sheets[@]}" = 0 ] ; then
            touch SampleSheet.csv.0
            echo "SampleSheet.csv.0 created as empty file"
            all_sheets=(SampleSheet.csv.0)
        fi
    fi
fi

# If SampleSheet.csv is now missing, link it to the latest sample sheet.
if [ ! -e SampleSheet.csv ] ; then
    ln -s "${all_sheets[ -1]}" SampleSheet.csv
fi

# At this point we may expect that SampleSheet.csv is a symlink. Sanity check.
if [ ! -L SampleSheet.csv ] ; then
    echo "Sanity check failed - SampleSheet.csv is not a symlink"
    #If the link was changed into a file (rsync was doing this at one point), try to undo the change
    if [ -e SampleSheet.csv ] ; then
        for candidate_ss in "${all_sheets[@]}" ; do
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

# Whatever happens, update the timestamp on the symlink. auto_redo.sh depends on this.
touch -h SampleSheet.csv

# Detect old and maybe ambiguous cases
if [ -e SampleSheet.csv.OVERRIDE ] ; then
    echo "Sample sheet overrides now need to go in the pipeline directory."
    echo "Please move SampleSheet.csv.OVERRIDE to the pipeline subdir then redo lanes."
    exit 1
fi

# Support OVERRIDE with local SampleSheet
if [ -e pipeline/SampleSheet.csv.OVERRIDE ] ; then
    echo "Giving priority to pipeline/SampleSheet.csv.OVERRIDE"

    ln -snf pipeline/SampleSheet.csv.OVERRIDE SampleSheet.csv
    echo "SampleSheet.csv for ${FLOWCELLID} is now linked to pipeline/SampleSheet.csv.OVERRIDE"
    exit 0
fi

# Special case to allow slim_a_run to work
if [ -e SampleSheet.csv.XOVERRIDE ] ; then
    echo "Giving priority to SampleSheet.csv.XOVERRIDE."

    ln -snf SampleSheet.csv.XOVERRIDE SampleSheet.csv
    echo "SampleSheet.csv for ${FLOWCELLID} is now linked to SampleSheet.csv.XOVERRIDE"
    exit 0
fi

# Grab the latest version of the sample sheet from Ragic
# Logic is:
# 1) If USE_RAGIC is not 'yes', print a warning and exit.
# 2) If samplesheet_from_ragic.py fails, exit with an error
# 3) If the new sample sheet is the same as SampleSheet.csv, keep the old one
# 4) If the new sample sheet is different, save a new one

if [ "${USE_RAGIC:-no}" != yes ] ; then
    echo "Not attempting to replace SampleSheet.csv as Ragic is not enabled"
    exit 0
fi

#Using noclobber to attempt writing to files until we find an unused name
set -o noclobber
counter=1
while ( ! true > "SampleSheet.csv.$counter" ) 2>/dev/null ; do
    counter=$(( $counter + 1 ))

    #  To break the loop in case there was some other write error
    test $counter -lt 1000
done
export SSPP_FILE="$(readlink -f "SampleSheet.csv.$counter")"
samplesheet_from_ragic.py --empty_on_missing -f "${UFLOWCELLID}" | \
    "$SSPP_HOOK" >> "SampleSheet.csv.$counter"
echo "Extracted new SampleSheet.csv.$counter from Ragic with filter ($SSPP_HOOK)"

if [ ! -s "SampleSheet.csv.$counter" ] ; then
    echo "New SampleSheet.csv for ${FLOWCELLID} is empty - ie. not found in Ragic"
    rm -f "SampleSheet.csv.$counter"
    exit 0
fi

# Now see if the new sheet is different. We do want to ignore the Date line because
# this can change if, for eg. we just push the run ID back.
if diff -I '^Date,' -q "SampleSheet.csv.$counter" SampleSheet.csv ; then
    echo "SampleSheet.csv for ${FLOWCELLID} is already up-to-date"
    rm -f "SampleSheet.csv.$counter"
    exit 0
fi

ln -sf "SampleSheet.csv.$counter" SampleSheet.csv # We earlier confirmed SampleSheet.csv is a link
echo "SampleSheet.csv for ${FLOWCELLID} is now linked to new SampleSheet.csv.$counter"

