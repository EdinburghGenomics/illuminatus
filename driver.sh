#!/bin/bash -l
set -e
set -u

# A driver script that is to be called directly from the CRON.
# It will go through all runs in SEQDATA_LOCATION and take action on them.
# As a well behaved CRON job it should only output error messages
# to stdout.
# The script wants to run every 5 minutes or so.

# This file must provide SEQDATA_LOCATION, FASTQ_LOCATION if not set externally.
if -e [ "`dirname $0`"/environ.sh ] ; then
    source "`dirname $0`"/environ.sh
fi

LOG_DIR="${LOG_DIR:-${HOME}/illuminatus/logs}"

BIN_LOCATION="${BIN_LOCATION:-$(dirname $0)}"
PATH="$(readlink -f $BIN_LOCATION):$PATH"
MAINLOG="${MAINLOG:-${LOG_DIR}/bcl2fastq_driver.`date +%Y%m%d`.log}"

# 1) Refuse to run on a machine other than headnode1
if [[ "${NO_HOST_CHECK:-0}" = 0 && "${HOSTNAME%%.*}" != headnode1 && "${HOSTNAME%%.*}" != gseg-login0 ]] ; then
    echo "This script should only be run on headnode1 or gseg-login0"
    echo "To skip this check set NO_HOST_CHECK=1"
    exit 1
fi

# 2) Ensure that the directory is there for the main log file and set up logging
mkdir -p `dirname "$MAINLOG"`
if [ "${MAINLOG:0:1}" != / ] ; then
    #Ensure abs path, because we change directories within this script
    MAINLOG="$(readlink -f "$MAINLOG")"
fi
log(){ [ $# = 0 ] && cat >> "$MAINLOG" || echo "$*" >> "$MAINLOG" ; }

trap 'echo "=== `date`. Finished run; PID=$$ ===" >> "$MAINLOG"' EXIT
log ""
log "=== `date`. Running $(readlink -f "$0"); PID=$$ ==="

# 3) Define an action for each possible status that a run can have:
# new)            - this run is seen for the first time (sequencing might be done or is still in progress)
# reads_incomplete) the run has been picked up by the pipeline but we're waiting for data
# reads_finished) - sequencing has finished, the pipeline/ folder exists the pipeline was not started yet...
# in_pipeline)    - the pipeline started processing at least one lane of this run but has not yet finished
# complete)       - the pipeline has finished processing ALL lanes of this run
# aborted)        - the run is not to be processed
# redo)           - at least one lane is marked for redo and run is complete
# unknown)        - anything else, including run folders without RunInfo.xml

# All actions can read LANES STATUS RUNID INSTRUMENT

action_new(){
    # Create a pipeline/ folder and make a sample sheet summary
    # For now the sample sheet summary will just be a copy of the sample sheet
    # If this works we can BREAK, but if not go on to process more runs

    # TODO - run initial MultiQC here.
    log "\_NEW $RUNID. Creating ./pipeline folder and making sample summary."
    ( set -e
      mkdir ./pipeline
      summarize_samplesheet.py > pipeline/sample_summary.txt
      rt_runticket_manager.py -r "$RUNID" --reply @pipeline/sample_summary.txt |& log

    ) && log OK && BREAK=1 || log FAIL
}

action_reads_unfinished(){
    log "\_READS_UNFINISHED $RUNID. Waiting for data."
}

action_reads_finished(){
    # Lock the run by writing pipeline/lane?.started per lane
    eval touch pipeline/"lane{1..$LANES}.started"
    log "\_READS_FINISHED $RUNID. Running samplesheet_fetch.sh"

    # Sort out the SampleSheet and replace with a new one from the LIMS if
    # available.
    samplesheet_fetch.sh |& log

    # Now kick off the demultiplexing into $FASTQ_LOCATION
    # TODO - add an interin MultiQC report now that the Interop files are here.
    BREAK=1
    DEMUX_OUTPUT_FOLDER="$FASTQ_LOCATION/$RUNID/demultiplexing/"
    log "Now starting demultiplexing for $RUNID into $DEMUX_OUTPUT_FOLDER"
    ( set -e
      mkdir -p "$DEMUX_OUTPUT_FOLDER"
      BCL2FASTQPreprocessor.py "`pwd`" "$DEMUX_OUTPUT_FOLDER" |& log
      cd "$DEMUX_OUTPUT_FOLDER"
      log "submitting to cluster..."
      BCL2FASTQRunner.sh | log 2>&1
      BCL2FASTQPostprocessor.py $DEMUX_OUTPUT_FOLDER $RUNID |& log

      rt_runticket_manager.py -r "$RUNID" --comment 'Demultiplexing completed'
    ) || log FAIL
}

# What about the transition from demultiplexing to QC. Do we need a new status,
# or is the QC part just hooked off the back of BCL2FASTQ?
# action_demultiplexing_finished() { ... }

# Also what about the copying to backup? I feel this should be an entirely separate
# RSYNC job. Maybe this script could hint at what needs to be copied to save running
# a full RSYNC again and again.

action_in_pipeline() {
    # in pipeline, could update some progress status
    # TODO - maybe some attempt to detect stalled runs?
    log "\_IN_PIPELINE $RUNID"
}

action_complete() {
    # the pipeline already completed for this run ... nothing to be done ...
    return
}

action_redo() {
    # Some lanes need to be re-done ...
    log "\_REDO $RUNID"

    # Get a list of what needs redoing.
    redo_list=""

    # Remove all .redo files and corresponding .done files
    for redo in $run/pipeline/lane?.redo ; do
        rm -f ${df%.redo}.done ; rm $df

        redo=${redo%.redo} ; redo=${redo##*[^0-9]}
        redo_list="$redo_list $redo"
    done

    (exit 1
     BCL2FASTQCleanup.py //args for partial cleanup here//
     BCL2FASTQPreprocessor.py "`pwd`" $DEMUX_OUTPUT_FOLDER $redo_list
     ( cd $DEMUX_OUTPUT_FOLDER && BCL2FASTQRunner.sh )
     BCL2FASTQPostprocessor.py $DEMUX_OUTPUT_FOLDER $RUNID
    ) && log OK && BREAK=1 || log FAIL
}

action_unknown() {
    # this run either has no RunInfo.xml or an invalid set of touch files ... nothing to be done...
    log "\_skipping `pwd` because status is $STATUS"
}

# 6) Scan for each run until we find something that needs dealing with.
for run in $SEQDATA_LOCATION/*_*_*_*/ ; do
  # invoke runinfo and collect some meta-information about the run. We're passing info
  # to the state functions via global variables.
  RUNINFO_OUTPUT="`RunInfo.py $run`"

  LANES=`grep ^LaneCount: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  STATUS=`grep ^Status: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  RUNID=`grep ^RunID: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  INSTRUMENT=`grep ^Instrument: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`

  log "Folder $run contains $RUNID from machine $INSTRUMENT with $LANES lane(s) and status $STATUS"

  #Call the appropriate function in the appropriate directory.
  BREAK=0
  { pushd "$run" >/dev/null && eval action_"$STATUS"
    popd >/dev/null
  } || log "Error while trying to scan $run"

  #If the function started some actual work it should request to break, as the CRON will start a new scan
  #soon in any case and we don't want runs overlapping.
  #Negated test is needed to play nicely with 'set -e'
  ! [ "$BREAK" = 1 ] || break
done

