#!/bin/bash

# This script will fetch a new SampleSheet for the current run. It must
# be run in the folder where the sequencer data has been written. For testing, try:
# $ cd ~/test_seqdata/170703_D00261_0418_ACB6HTANXX/ ; samplesheet_fetch.sh
set -euo pipefail
shopt -s nullglob

# The $PATH should be set by the driver, but to allow this script to be run standalone:
if ! which RunStatus.py >&/dev/null ; then
    PATH="$(readlink -f $(dirname "$BASH_SOURCE")):$PATH"
fi

# Support a SampleSheet postprocessor hook. This must take one argument,
# the file to be read, and print to stdout. I'm not really using this in production
# since the samplesheets are now specifically generated for this pipeline.
SSPP_HOOK="${SSPP_HOOK:-}"

if [ -z "${FLOWCELLID:-}" ] ; then
    #Try to determine flowcell ID by asking RunStatus.py
    FLOWCELLID=$(RunStatus.py | grep '^Flowcell:' | cut -f2 -d' ') || true
fi

if [ -z "${FLOWCELLID:-}" ] ; then
    echo "No FLOWCELLID was provided, and obtaining one from RunStatus.py failed."
    exit 1
fi

# Zerothly, remove any dangling symlink
if [ ! -e SampleSheet.csv ] ; then
    rm -f SampleSheet.csv
fi

# List the sample sheet files we do see
all_sheets=(SampleSheet.csv.[0-9]*)

# SampleSheet.csv.0 needs to contain the original file from the
# sequencer. It is also possible to run the machine with no sample
# sheet. In this case, if there is nothing at all, this script will make an empty file.
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
    echo "Giving priority to pipeline/SampleSheet.csv.OVERRIDE."

    ln -snf pipeline/SampleSheet.csv.OVERRIDE SampleSheet.csv
    echo "SampleSheet.csv for ${FLOWCELLID} is now linked to pipeline/SampleSheet.csv.OVERRIDE."
    exit 0
fi

# Special case to allow slim_a_run to work
if [ -e SampleSheet.csv.XOVERRIDE ] ; then
    echo "Giving priority to SampleSheet.csv.XOVERRIDE."

    ln -snf SampleSheet.csv.XOVERRIDE SampleSheet.csv
    echo "SampleSheet.csv for ${FLOWCELLID} is now linked to SampleSheet.csv.XOVERRIDE."
    exit 0
fi

# Find a candidate sample sheet, from the files on /ifs/clarity (or wherever)
# New logic here is:
# 1) If SAMPLESHEETS_ROOT is set use that
# 2) Else if SAMPLESHEETS_ROOT is set by .genologicsrc use that
# 3) Else complain and exit (but not with an error as before)
# 4) If the directory is set but not found, exit with an error

if [ -z "${SAMPLESHEETS_ROOT:-}" ] ; then
    # Read the Genologics configuration with the same priorities as the LIMSQuery.py code.
    # This is a bit hacky, but it is effective.
    eval `grep -h '^SAMPLESHEETS_ROOT=' /etc/genologics.conf genologics.cfg genologics.conf ~/.genologicsrc ${GENOLOGICSRC:-/dev/null} 2>/dev/null`
fi
# Is it set now?
if [ -z "${SAMPLESHEETS_ROOT:-}" ] || [ "${SAMPLESHEETS_ROOT}" = none  ] ; then
    echo "Not attempting to replace SampleSheet.csv as no \$SAMPLESHEETS_ROOT was set."
    exit 0
else
    if ! [ -d "${SAMPLESHEETS_ROOT}" ] ; then
        echo "No such directory SAMPLESHEETS_ROOT=${SAMPLESHEETS_ROOT}. Check your .genologiscrc file." | tee >(cat >&2)
        exit 1
    fi
fi

# The latest one that matches the flowcell ID is the one we want.
# Or do we want to sort on some other criterion?
candidate_ss=$(find "$SAMPLESHEETS_ROOT" -name "*_*.csv" -print0 | \
               { egrep -zi "_${FLOWCELLID}\.csv$" || true ; } | \
               xargs -r0 ls -tr -- | tail -n 1)

if [ ! -e "$candidate_ss" ] ; then
    echo "No candidate replacement samplesheet for ${FLOWCELLID} under $SAMPLESHEETS_ROOT"
elif [ -z "$SSPP_HOOK" ] && diff -q "$candidate_ss" SampleSheet.csv ; then
    #Nothing to do.
    echo "SampleSheet.csv for ${FLOWCELLID} is already up-to-date"
else
    #Using noclobber to attempt writing to files until we find an unused name
    set -o noclobber
    counter=1
    while ( ! true > "SampleSheet.csv.$counter" ) 2>/dev/null ; do
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

