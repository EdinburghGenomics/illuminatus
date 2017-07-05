#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

# A driver script that is to be called directly from the CRON.
# It will go through all runs in SEQDATA_LOCATION and take action on them.
# As a well behaved CRON job it should only output error messages
# to stdout.
# The script wants to run every 5 minutes or so.

# This file must provide SEQDATA_LOCATION, FASTQ_LOCATION if not set externally.
if [ -e "`dirname $BASH_SOURCE`"/environ.sh ] ; then
    pushd "`dirname $BASH_SOURCE`" >/dev/null
    source ./environ.sh
    popd >/dev/null
fi

LOG_DIR="${LOG_DIR:-${HOME}/illuminatus/logs}"
RUN_NAME_PATTERN="${RUN_NAME_PATTERN:-*_*_*_*}"

BIN_LOCATION="${BIN_LOCATION:-$(dirname $0)}"
PATH="$(readlink -m $BIN_LOCATION):$PATH"
MAINLOG="${MAINLOG:-${LOG_DIR}/bcl2fastq_driver.`date +%Y%m%d`.log}"

# 1) Refuse to run on a machine other than headnode1
# (do we really still need this??)
if [[ "${NO_HOST_CHECK:-0}" = 0 && "${HOSTNAME%%.*}" != headnode1 && "${HOSTNAME%%.*}" != gseg-login0 ]] ; then
    echo "This script should only be run on headnode1 or gseg-login0"
    echo "To skip this check set NO_HOST_CHECK=1"
    exit 1
fi

# 1a) Sanity check these directories exist and complain to STDERR (triggering CRON
#     warning mail) if not.
for d in "${BIN_LOCATION%%:*}" "$SEQDATA_LOCATION" "$FASTQ_LOCATION" ; do
    if ! [ -d "$d" ] ; then
        echo "No such directory '$d'" >&2
        exit 1
    fi
done

# 2) Ensure that the directory is there for the main log file and set up logging
#    on file descriptor 5.
mkdir -p `dirname "$MAINLOG"` ; exec 5>>"$MAINLOG"

# Main log for general messages (STDERR still goes to the CRON).
log(){ [ $# = 0 ] && cat >&5 || echo "$*" >&5 ; }

# Per-project log for project progress messages
plog() {
    projlog="$SEQDATA_LOCATION/${RUNID:-NO_RUN_SET}/pipeline/pipeline.log"
    if ! { [ $# = 0 ] && cat >> "$projlog" || echo "$*" >> "$projlog" ; } ; then
       log '!!'" Failed to write to $projlog"
       log "$@"
    fi
}

plog_start() {
    plog $'>>>\n>>>\n>>>'" $0 starting action_$STATUS at `date`"
}

# Print a message at the top of the log, and trigger one to print at the end.
intro="`date`. Running $(readlink -f "$0"); PID=$$"
log "====`tr -c '' = <<<$intro`===="
log "=== $intro ==="
log "====`tr -c '' = <<<$intro`===="
trap 'log "=== `date`. Finished run; PID=$$ ==="' EXIT

# If there is a Python VEnv, use it.
py_venv="${BIN_LOCATION%%:*}/_py3_venv"
if [ -e "${py_venv}/bin/activate" ] ; then
    log "Activating Python VEnv from ${py_venv}"
    reset=`set +o | grep -w nounset` ; set +o nounset
    source "${py_venv}/bin/activate"
    $reset
fi

# 3) Define an action for each possible status that a run can have:
# new)            - this run is seen for the first time (sequencing might be done or is still in progress)
# reads_incomplete) the run has been picked up by the pipeline but we're waiting for data
# reads_finished) - sequencing has finished, the pipeline/ folder exists the pipeline was not started yet...
# in_pipeline)    - the pipeline started processing at least one lane of this run but has not yet finished
# complete)       - the pipeline has finished processing ALL lanes of this run
# aborted)        - the run is not to be processed
# failed)         - the pipeline tried to process the run but failed
# redo)           - at least one lane is marked for redo and run is complete or failed
# unknown)        - anything else, including run folders without RunInfo.xml

# All actions can read LANES STATUS RUNID INSTRUMENT

action_new(){
    # Create a pipeline/ folder and make a sample sheet summary
    # For now the sample sheet summary will just be a copy of the sample sheet
    # If this works we can BREAK, but if not go on to process more runs

    # TODO - run initial MultiQC here.
    log "\_NEW $RUNID. Creating ./pipeline folder and making sample summary."
    set +e ; ( set -e
      mkdir ./pipeline
      plog_start
      fetch_samplesheet_and_report

    ) ; [ $? = 0 ] && log OK && BREAK=1 || log FAIL
}

action_reads_unfinished(){
    log "\_READS_UNFINISHED $RUNID. Waiting for data."
}

action_reads_finished(){
    # Lock the run by writing pipeline/lane?.started per lane
    eval touch pipeline/"lane{1..$LANES}.started"
    log "\_READS_FINISHED $RUNID. Checking for new SampleSheet.csv and preparing to demultiplex."
    plog_start

    # Sort out the SampleSheet and replace with a new one from the LIMS if
    # available.
    fetch_samplesheet_and_report

    # Now kick off the demultiplexing into $FASTQ_LOCATION
    # Note that the preprocessor and runner are not aware of the 'demultiplexing'
    # subdirectory and need to be passed the full location explicitly.
    # The postprocessor does expect to fingd the files in a 'demultiplexing'
    # subdirectory. This is for 'good reasons' (TM).
    # TODO - add an interim MultiQC report now that the Interop files are here.
    BREAK=1
    DEMUX_OUTPUT_FOLDER="$FASTQ_LOCATION/$RUNID"
    export DEMUX_JOBNAME="demux_${RUNID}"
    plog "Preparing to demultiplex $RUNID into $DEMUX_OUTPUT_FOLDER/demultiplexing/"
    set +e ; ( set -e
      mkdir -p "$DEMUX_OUTPUT_FOLDER"/demultiplexing
      BCL2FASTQPreprocessor.py . "$DEMUX_OUTPUT_FOLDER"/demultiplexing
      log "  Starting bcl2fastq on $RUNID."
      cd "$DEMUX_OUTPUT_FOLDER"/demultiplexing
      BCL2FASTQRunner.sh |& plog
      BCL2FASTQPostprocessor.py "$DEMUX_OUTPUT_FOLDER" $RUNID

      log "  Completed bcl2fastq on $RUNID."
      rt_runticket_manager.py -r "$RUNID" --comment 'Demultiplexing completed'
    ) |& plog ; [ $? = 0 ] || demux_fail
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

action_failed() {
    # failed runs need attention, but for now just log the situatuion
    log "\_FAILED $RUNID"
}

action_aborted() {
    true
}

action_complete() {
    # the pipeline already completed for this run ... nothing to be done ...
    true
}

action_redo() {
    # Some lanes need to be re-done ...
    log "\_REDO $RUNID"
    plog_start

    # Get a list of what needs redoing.
    redo_list=()

    # Remove all .redo files and corresponding .done files
    for redo in pipeline/lane?.redo ; do
        rm -f ${redo%.redo}.done ; rm $redo

        [[ "$redo" =~ .*(.)\.redo ]]
        redo_list+=(${BASH_REMATCH[1]})
    done
    redo_str="lanes`tr -d ' ' <<<${redo_list[*]}`"

    # Re-summarize the sample sheet, as it probably changed.
    # TODO - say what lanes are being demuxed in the report, since we can't just now promise
    # that all the altered lanes are the actual ones being re-done.
    fetch_samplesheet_and_report

    BREAK=1
    DEMUX_OUTPUT_FOLDER="$FASTQ_LOCATION/$RUNID"
    export DEMUX_JOBNAME="demux_${RUNID}_${redo_str}"
    set +e ; ( set -e
      if [ -e "$DEMUX_OUTPUT_FOLDER" ] ; then
        BCL2FASTQCleanup.py "$DEMUX_OUTPUT_FOLDER" "${redo_list[@]}"
      fi
      mkdir -p "$DEMUX_OUTPUT_FOLDER"/demultiplexing
      BCL2FASTQPreprocessor.py . "$DEMUX_OUTPUT_FOLDER"/demultiplexing "${redo_list[@]}"

      log "  Starting bcl2fastq on $RUNID lanes ${redo_list[*]}."
      cd "$DEMUX_OUTPUT_FOLDER"/demultiplexing
      BCL2FASTQRunner.sh |& plog
      BCL2FASTQPostprocessor.py "$DEMUX_OUTPUT_FOLDER" $RUNID

      log "  Completed demultiplexing on $RUNID lanes ${redo_list[*]}."
      rt_runticket_manager.py -r "$RUNID" --comment "Re-Demultiplexing of lanes ${redo_list[*]} completed"
    ) |& plog ; [ $? = 0 ] || demux_fail
}

action_unknown() {
    # this run either has no RunInfo.xml or an invalid set of touch files ... nothing to be done...
    log "\_skipping `pwd` because status is $STATUS"
}

### Other utility functions used by the actions.
fetch_samplesheet_and_report() {
    # Tries to fetch an updated samplesheet. If this is the first run, or if
    # a new one was found, send an e-mail report to RT.
    # TODO - trigger an initial MultiQC report too.
    old_ss_link="`readlink -q SampleSheet.csv || true`"

    #Currently if samplesheet_fetch.sh returns an error the pipeline aborts.
    samplesheet_fetch.sh | plog
    new_ss_link="`readlink -q SampleSheet.csv || true`"

    if [ ! -e pipeline/sample_summary.txt ] || \
       [ "$old_ss_link" != "$new_ss_link" ] ; then
        summarize_samplesheet.py > pipeline/sample_summary.txt
        rt_runticket_manager.py -r "$RUNID" --reply @pipeline/sample_summary.txt |& plog
    fi
}

demux_fail() {
    # Mark the failure status
    touch pipeline/failed

    # Send an alert when demultiplexing fails. This always requires attention!
    # Note that after calling 'plog' we can query '$projlog' since all shell vars are global.
    plog "Attempting to notify error to RT"
    if rt_runticket_manager.py -r "$RUNID" --reply "Demultiplexing failed. See log in $projlog" |& plog ; then
        log "FAIL processing $RUNID. See $projlog"
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL processing $RUNID, and also failed to report the error via RT. See $projlog"
        echo "$msg" >&2
        log "$msg"
    fi
}

# 6) Scan for each run until we find something that needs dealing with.
for run in "$SEQDATA_LOCATION"/$RUN_NAME_PATTERN/ ; do
  # invoke runinfo and collect some meta-information about the run. We're passing info
  # to the state functions via global variables.
  RUNINFO_OUTPUT="`RunInfo.py $run`"

  LANES=`grep ^LaneCount: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  STATUS=`grep ^Status: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  RUNID=`grep ^RunID: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  INSTRUMENT=`grep ^Instrument: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  FLOWCELLID=`grep ^Flowcell: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`

  log "Directory $run contains $RUNID from machine $INSTRUMENT with $LANES lane(s) and status=$STATUS"

  #Call the appropriate function in the appropriate directory.
  BREAK=0
  { pushd "$run" >/dev/null && eval action_"$STATUS" &&
    popd >/dev/null
  } || log "Error while trying to scan $run"
  #in case it got clobbered...
  set -e

  # If the driver started some actual work it should request to break, as the CRON will start
  # a new scan at regular intervals in any case. We don't want an instance of the driver to
  # spend 2 hours demultiplexing then start working on a new run. On the other hand, we don't
  # want a problem run to gum up the pipeline if every instance of the script tries to process
  # it, fails, and then exits.
  # Negated test is needed to play nicely with 'set -e'
  ! [ "$BREAK" = 1 ] || break
done

