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
htlb=12

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
candidate_ss=(`find $SAMPLESHEETS_ROOT/$(date +'%Y/%-m') -name '*_*.csv' -mmin -$(( $htlb * 60 ))`)
echo "Checking ${#candidate_ss[@]} files."

for ss in "${candidate_ss[@]}" ; do
    # For each of these we need the FCID and also the timestamp.
    # This pattern is guaranteed to match
    [[ `basename "$ss"` =~ _([^_]+)\.csv$ ]]
    fcid="${BASH_REMATCH[1]}"
    ts=`stat -c %Z "$ss"`

    echo "Checking $ss ($fcid@$ts)"

    # See if there is a matching run, accounting for the naming differences between MiSeq and HiSeq/NovaSeq
    seqdir="`ls -d $SEQDATA_LOCATION/*_?$fcid  /lustre/seqdata/*-$fcid 2>/dev/null || true`"
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
    old_ts=`stat -c %Z "$seqdir/SampleSheet.csv"`
    if [ "$ts" -le "$old_ts" ] ; then
        echo "The candidate sheet is not newer than $seqdir/SampleSheet.csv"
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
