#!/bin/bash
set -euo pipefail

# This script implements the logic described in doc/auto_lane_restart.txt
# It borrows a few things from the (undocumented) redo.sh and samplesheet_fetch.sh scripts.
if [ "${DRY_RUN:-0}" != 0 ] ; then
    echorun() { echo DRY_RUN: "$*" ; }
else
    echorun() { echo "$*" ; "$@" ; }
fi


if [ -z "${SAMPLESHEETS_ROOT:-}" ] ; then
    # Read the Genologics configuration with the same priorities as the LIMSQuery.py code.
    # This is a bit hacky, but it is effective.
    eval `grep -h '^SAMPLESHEETS_ROOT=' /etc/genologics.conf genologics.cfg genologics.conf ~/.genologicsrc ${GENOLOGICSRC:-/dev/null} 2>/dev/null`
fi
# If it's not set now it's an error.
if [ -z "${SAMPLESHEETS_ROOT:-}" ] ; then
    echo "No SAMPLESHEETS_ROOT was set in either the environment or GENOLOGICSRC."
    exit 1
else
    if ! [ -d "${SAMPLESHEETS_ROOT}" ] ; then
        echo "No such directory SAMPLESHEETS_ROOT=${SAMPLESHEETS_ROOT}. Check your .genologiscrc file." | tee >(cat >&2)
        exit 1
    fi
fi

# SEQDATA_LOCATION must be set too.
echo "Looking for new samplesheets in ${SAMPLESHEETS_ROOT} that relate to completed runs in ${SEQDATA_LOCATION}"

# And ensure up front that RunStatus.py is in the path
which RunStatus.py >/dev/null

# Number of Hours To Look Back
htlb="${REDO_HOURS_TO_LOOK_BACK:-12}"

redo_run(){
    # Re-do a run we are sure needs restarting
    _seqdir="$1"
    _status="$2"
    _lanes="$3"

    if [ "$_status" = failed ] ; then
        # Policy dictates we redo all the lanes
        lc=$(RunStatus.py "$_seqdir" | grep ^LaneCount: | cut -f2 -d' ' || echo 0)
        _lanes=`seq 1 $lc`
    fi

    # Given the earlier status check, there should not be any redo files present
    for l in $_lanes ; do
        echorun touch "$_seqdir/pipeline/lane${l}.redo"
    done
}

# Find all the samplesheets that were created in the last 12 hours (assuming nobody makes one at
# midnight on the last day of the month!)
samplesheets_this_month="$SAMPLESHEETS_ROOT/$(date +'%Y/%-m')"
if [ ! -e "$samplesheets_this_month" ] ; then
    # Not an error, we just have no new stuff yet
    echo "No such directory $samplesheets_this_month"
    exit 0
fi

# Robustly capture the list of files from find. See:
# https://stackoverflow.com/questions/1116992/capturing-output-of-find-print0-into-a-bash-array
candidate_ss=()
while IFS= read -r -d '' file ; do candidate_ss+=("$file") ; done < \
    <( find "$samplesheets_this_month" -name '*_*.csv' -mmin -$(( $htlb * 60 )) -print0 )

# Just to tidy up the messages when there are no files to scan.
if [ "${VERBOSE:-0}" = 0 ] ; then
    [[ ${#candidate_ss[@]} != 0 ]] || exit 0
fi

echo "Checking ${#candidate_ss[@]} files."

set +u ; for ss in "${candidate_ss[@]}" ; do set -u
    # For each of these we need the FCID and also the timestamp (%Y not %Z!).
    # This pattern is guaranteed to match
    [[ `basename "$ss"` =~ _([^_]+)\.csv$ ]]
    fcid="${BASH_REMATCH[1]}"
    ts=`stat -c %Y "$ss"`

    echo "Checking $ss ($fcid@$ts)"

    # See if there is a matching run, accounting for the naming differences between MiSeq and HiSeq/NovaSeq
    seqdir="`ls -d "$SEQDATA_LOCATION"/*_?$fcid  "$SEQDATA_LOCATION"/*-$fcid 2>/dev/null || true`"
    if [ ! -d "$seqdir" ] ; then
        echo "No directory found in $SEQDATA_LOCATION for FCID $fcid"
        continue
    fi

    # Check the run status
    status=`RunStatus.py "$seqdir" | grep ^PipelineStatus: | cut -f2 -d' ' || echo unknown`
    #echo "$seqdir $status"

    if ! [ "$status" == complete -o "$status" == failed ] ; then
        echo "Will not touch run in status $status"
        continue
    fi

    # Check the timestamp. If the SampleSheet.csv link is newer than this sheet then
    # we risk sending the pipeline round in a repeating loop (I've modified the samplesheet_fetcher to always
    # touch the file so it's a reasonable reflection of the last run time).
    # If the sample sheet is re-generated just after the fetch, the status test above will fail until
    # the pipeline fails or completes, but then the run will become a candidate for restarting. This is desirable.
    if ! [ -L "$seqdir/SampleSheet.csv" ] ; then
        echo "Sanity check failed - $seqdir/SampleSheet.csv is not a symlink"
        continue
    fi
    # No restart, as override is in effect.
    if [ "$(basename $(readlink "$seqdir/SampleSheet.csv"))" = SampleSheet.csv.OVERRIDE ] ; then
        echo "OVERRIDE is in effect ($seqdir/SampleSheet.csv -> $(readlink "$seqdir/SampleSheet.csv"))"
        continue
    fi

    # Remember stat on the command line is actually lstat (as opposed to stat -L)
    old_ts=`stat -c %Y "$seqdir/SampleSheet.csv"`
    if [ "$ts" -le "$old_ts" ] ; then
        echo "The candidate sheet is not newer than $seqdir/SampleSheet.csv (@$old_ts)"
        continue
    fi

    # See which lanes, if any, were changed.
    changes=$( diff -Z --old-line-format='%L' --new-line-format='%L' --unchanged-line-format='' \
                "$seqdir/SampleSheet.csv" "$ss" | sed -n 's/^\([0-9]\)\+,.*/\1/p' | uniq || true )
    if [ -z "$changes" ] ; then
        echo "No changes compared to $seqdir/SampleSheet.csv"
        continue
    fi

    # So after all that checking, we do want to restart the run.
    redo_run "$seqdir" "$status" "$changes"
done

echo "DONE"
