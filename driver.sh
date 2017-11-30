#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

# A driver script that is to be called directly from the CRON.
# It will go through all runs in SEQDATA_LOCATION and take action on them.
# As a well behaved CRON job it should only output error messages
# to stdout.
# The script wants to run every 5 minutes or so, and having multiple instances
# in flight at once if fine, though in fact there are race conditions possible if two
# instances start at once and claim the same run for processing (Snakemake locking
# should catch any fallout).

# Note within this script I've tried to use ( subshell blocks ) along with "set -e"
# to emulate eval{} statements in Perl. It does work but you have to be really careful
# on the syntax, and you have to check $? explicitly - trying to do it implicitly in
# the manner of ( foo ) || handle_error won't do what you expect.

# For the sake of the unit tests, we must be able to skip loading the config file,
# so allow the location to be set to, eg. /dev/null
ENVIRON_SH="${ENVIRON_SH:-`dirname $BASH_SOURCE`/environ.sh}"

# This file must provide SEQDATA_LOCATION, FASTQ_LOCATION if not set externally.
if [ -e "$ENVIRON_SH" ] ; then
    pushd "`dirname $ENVIRON_SH`" >/dev/null
    source "`basename $ENVIRON_SH`"
    popd >/dev/null
fi

LOG_DIR="${LOG_DIR:-${HOME}/illuminatus/logs}"
RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"

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
log(){ [ $# = 0 ] && cat >&5 || echo "$@" >&5 ; }

# Debug means log only if VERBOSE is set
debug(){ if [ "${VERBOSE:-0}" != 0 ] ; then log "$@" ; else [ $# = 0 ] && cat >/dev/null || true ; fi ; }

# Per-project log for project progress messages, goes into the output
# directory.
# Unfortunately this can get scrambled if we try to run read1 processing and demux
# at the same time, so have a plog1 for that.
plog() {
    projlog="$DEMUX_OUTPUT_FOLDER/pipeline.log"
    if ! { [ $# = 0 ] && cat >> "$projlog" || echo "$*" >> "$projlog" ; } ; then
       log '!!'" Failed to write to $projlog"
       log "$@"
    fi
}

# Have a special log for the read1 processing, as this can happen in parellel
# with other actions.
plog1() {
    projlog1="$DEMUX_OUTPUT_FOLDER/pipeline_read1.log"
    if ! { [ $# = 0 ] && cat >> "$projlog1" || echo "$*" >> "$projlog1" ; } ; then
       log '!!'" Failed to write to $projlog1"
       log "$@"
    fi
}

plog_start() {
    mkdir -vp "$DEMUX_OUTPUT_FOLDER" |& debug
    plog $'>>>\n>>>\n>>>'" $0 starting action_$STATUS at `date`"
}

# Print a message at the top of the log, and trigger one to print at the end.
intro="`date`. Running $(readlink -f "$0"); PID=$$"
log "====`tr -c '' = <<<$intro`==="
log "=== $intro ==="
log "====`tr -c '' = <<<$intro`==="
trap 'log "=== `date`. Finished run; PID=$$ ==="' EXIT

# If there is a Python VEnv, use it.
py_venv="${BIN_LOCATION%%:*}/_py3_venv"
if [ -e "${py_venv}/bin/activate" ] ; then
    log -n "Activating Python VEnv from ${py_venv}"
    reset=`set +o | grep -w nounset` ; set +o nounset
    source "${py_venv}/bin/activate"
    log '...DONE'
    $reset
fi

# 3) Define an action for each possible status that a run can have:
# new)            - this run is seen for the first time (sequencing might be done or is still in progress)
# reads_unfinished) the run has been picked up by the pipeline but we're waiting for data
# read1_finished) - the run is ready for post-read1 qc (ie. well dupe counting)
# in_read1_qc)    - read 1 qc is underway
# reads_finished) - sequencing has finished, the pipeline/ folder exists the pipeline was not started yet...
# in_demultiplexing) the pipeline started [re-]demultiplexing at least one lane of this run but has not yet finished
# demultiplexed)  - the demultiplexing (bcl2fastq) part finished. QC is still needed.
# in_qc)          - the QC part of the pipeline is running. In the meantime, the sequences may be used.
# complete)       - the pipeline has finished processing ALL lanes of this run, including QC
# aborted)        - the run is not to be processed
# failed)         - the pipeline tried to process the run but failed
# redo)           - at least one lane is marked for redo and run is complete or failed
# unknown)        - anything else, including run folders without RunInfo.xml

# All actions can read LANES STATUS RUNID INSTRUMENT

action_new(){
    # Create a pipeline/ folder and make a sample sheet summary
    # For now the sample sheet summary will just be a copy of the sample sheet
    # If this works we can BREAK, but if not go on to process more runs

    # In order to run the initial round of MultiQC we'll also end up making the
    # $DEMUX_OUTPUT_FOLDER/QC/ directory. The symlink ./pipeline/output will
    # be made to point to this.
    # We're now sending the logs to the output folder too.
    log "\_NEW $RUNID. Creating ./pipeline folder and making sample summary."
    set +e ; ( set -e
      mkdir -v ./pipeline |& debug
      ln -sv "$DEMUX_OUTPUT_FOLDER" ./pipeline/output |& debug

      plog_start
      fetch_samplesheet
      run_multiqc | plog

      # Add a link back in the other direction, now the output folder is there.
      ln -sv "`pwd -P`" "$DEMUX_OUTPUT_FOLDER"/seqdata
    ) ; [ $? = 0 ] && log OK && BREAK=1 || log FAIL
}

action_reads_unfinished(){
    log "\_READS_UNFINISHED $RUNID. Waiting for data."
}

action_reads_finished(){
    # Lock the run by writing pipeline/lane?.started per lane
    # Note this action must not attempt to run any QC ops - an interim report will be triggered
    # by action_demultiplexed before it fires off all the QC jobs.
    eval touch pipeline/"lane{1..$LANES}.started"

    log "\_READS_FINISHED $RUNID. Checking for new SampleSheet.csv and preparing to demultiplex."
    plog_start

    # Log the start in a way we can easily read back (humans can check the main log!)
    date >>pipeline/start_times

    # Sort out the SampleSheet and replace with a new one from the LIMS if
    # available.
    fetch_samplesheet
    ( run_multiqc | plog ) || true

    # Now kick off the demultiplexing into $FASTQ_LOCATION
    # Note that the preprocessor and runner are not aware of the 'demultiplexing'
    # subdirectory and need to be passed the full location explicitly.
    # The postprocessor does expect to find the files in a 'demultiplexing'
    # subdirectory. This is for 'good reasons' (TM).
    BREAK=1
    plog "Preparing to demultiplex $RUNID into $DEMUX_OUTPUT_FOLDER/demultiplexing/"
    set +e ; ( set -e
      mkdir -vp "$DEMUX_OUTPUT_FOLDER"/demultiplexing
      log "  Starting bcl2fastq on $RUNID."
      ( rundir="`pwd`"
        cd "$DEMUX_OUTPUT_FOLDER"/demultiplexing
        Snakefile.demux --config lanes="$(echo `seq $LANES`)" rundir="$rundir"
      ) |& plog

      for f in pipeline/lane?.started ; do
          mv $f ${f%.started}.done
      done
      rt_runticket_manager.py -r "$RUNID" --comment 'Demultiplexing completed'
      log "  Completed bcl2fastq on $RUNID."

    ) |& plog ; [ $? = 0 ] || pipeline_fail Demultiplexing
}

action_in_read1_qc_reads_finished(){
    #Same as above
    debug "\_IN_READ1_QC_READS_FINISHED $RUNID"

    action_reads_finished
}

# What about the transition from demultiplexing to QC. Do we need a new status,
# or is the QC part just hooked off the back of BCL2FASTQ?
# I say the former, or else it is harder to re-run QC without re-demultiplexing,
# and also to see exactly where the run is.
action_demultiplexed() {
    log "\_DEMULTIPLEXED $RUNID"
    log "  Now commencing QC on $RUNID."

    # This touch file puts the run into status in_qc.
    touch pipeline/qc.started
    BREAK=1
    set +e ; ( set -e
        run_qc

        log "  Completed QC on $RUNID."
        mv pipeline/qc.started pipeline/qc.done

        rt_runticket_manager.py -r "$RUNID" --comment "QC of $RUNID completed"
    ) |& plog ; [ $? = 0 ] || pipeline_fail QC
}

# Also what about the copying to backup? I feel this should be an entirely separate
# RSYNC job. Maybe this script could hint at what needs to be copied to save running
# a full RSYNC again and again.

action_in_demultiplexing() {
    # in pipeline, could update some progress status
    # TODO - maybe some attempt to detect stalled runs?
    debug "\_IN_DEMULTIPLEXING $RUNID"
}

action_read1_finished() {
    debug "\_READ1_FINISHED $RUNID"
    log "  Now commencing read1 processing on $RUNID."

    touch pipeline/read1.started
    plog_start
    plog "See pipeline_read1.log for details on that."
    plog1 </dev/null  #Log1 must be primed before entering subshell!

    # Now is the time for WellDups scanning. Note that we press on despite failure,
    # since we don't want a problem here to hold up demultiplexing.
    # There will be a retry at the point of QC with stricter error handling.
    mkdir -vp "$DEMUX_OUTPUT_FOLDER"/QC |& debug
    BREAK=1
    set +e ; ( set +e
        rundir="`pwd`"
        e=''
        cd "$DEMUX_OUTPUT_FOLDER"
        Snakefile.welldups --config rundir="$rundir" -- wd_main || e="$e welldups"
        Snakefile.qc -- interop_main                            || e="$e interop"
        cd "$rundir" ; run_multiqc                              || e="$e multiqc"

        if [ -n "$e" ] ; then
            log "  There were errors in read1 processing (${e# }) on $RUNID. See $projlog1"
        else
            log "  Completed read1 processing on $RUNID."
        fi
    ) |& plog1

    # We're done. If the above block was interrupted by SIGINT we'll arrive here
    # with $? set to 130. Log the interruption but still set the done flag as the state
    # diagram demands it.
    if [ "$?" != 0 ] ; then
        plog1 "Interrupted during read1 processing on $RUNID."
        log "  Interrupted during read1 processing on $RUNID."
    fi

    mv pipeline/read1.started pipeline/read1.done
}

action_in_read1_qc() {
    debug "\_IN_READ1_QC $RUNID"
}

action_in_qc() {
    debug "\_IN_QC $RUNID"
}

action_failed() {
    # failed runs need attention, but for now just log the situatuion
    log "\_FAILED $RUNID (`cat pipeline/failed`)"
}

action_aborted() {
    true
}

action_complete() {
    # the pipeline already fully completed for this run ... nothing to be done ...
    true
}

action_redo() {
    # Some lanes need to be re-done. Complicated...
    log "\_REDO $RUNID"
    plog_start

    # Log the start in a way we can easily read back (humans can check the main log!)
    date >>pipeline/start_times

    # Get a list of what needs redoing.
    redo_list=()

    # Remove all .redo files and corresponding .done files
    # Also remove ALL old .started files since once the failed file is gone the
    # system will think these are really running. (Nothing should be running just now!)
    ( rm -f pipeline/lane?.started ) 2>/dev/null || true
    for redo in pipeline/lane?.redo ; do
        touch ${redo%.redo}.started
        rm -f ${redo%.redo}.done ; rm $redo

        [[ "$redo" =~ .*(.)\.redo ]]
        redo_list+=(${BASH_REMATCH[1]})
    done
    # Clean out all the other flags, then the actual data.
    rm -f pipeline/qc.started pipeline/qc.done pipeline/failed pipeline/aborted

    BREAK=1  # If we fail after this, don't try to process more runs on this cycle.
    set +e ; ( set -e
      if [ -e "$DEMUX_OUTPUT_FOLDER" ] ; then
        BCL2FASTQCleanup.py "$DEMUX_OUTPUT_FOLDER" "${redo_list[@]}"
      fi
    ) |& plog ; [ $? = 0 ] || pipeline_fail Cleanup_for_Re-demultiplexing

    # Re-summarize the sample sheet, as it probably changed.
    # TODO - say what lanes are being demuxed in the report, since we can't just now promise
    # that all the altered lanes are the actual ones being re-done.
    fetch_samplesheet
    run_multiqc | plog

    set +e ; ( set -e
      mkdir -vp "$DEMUX_OUTPUT_FOLDER"/demultiplexing

      log "  Starting bcl2fastq on $RUNID lanes ${redo_list[*]}."
      ( rundir="`pwd`"
        cd "$DEMUX_OUTPUT_FOLDER"/demultiplexing
        Snakefile.demux --config lanes="${redo_list[*]}" rundir="$rundir"
      ) |& plog

      for f in pipeline/lane?.started ; do
          mv $f ${f%.started}.done
      done
      rt_runticket_manager.py -r "$RUNID" --comment "Re-Demultiplexing of lanes ${redo_list[*]} completed"
      log "  Completed demultiplexing on $RUNID lanes ${redo_list[*]}."

    ) |& plog ; [ $? = 0 ] || pipeline_fail Re-demultiplexing

}

action_unknown() {
    # this run either has no RunInfo.xml or an invalid set of touch files ... nothing to be done...
    log "\_skipping `pwd` because status is $STATUS"
}

### Other utility functions used by the actions.
fetch_samplesheet(){
    # Tries to fetch an updated samplesheet. If this is the first run, or if
    # a new one was found, delete the stale sample_summary.yml.
    old_ss_link="`readlink -q SampleSheet.csv || true`"

    #Currently if samplesheet_fetch.sh returns an error the pipeline aborts, as
    #this indicates a fundamental problem.
    samplesheet_fetch.sh | plog
    new_ss_link="`readlink -q SampleSheet.csv || true`"

    if [ "$old_ss_link" != "$new_ss_link" ] ; then
        rm -vf pipeline/sample_summary.yml |& debug
    fi
}

run_multiqc() {
    # Runs multiqc. Will not exit on error.
    # Caller is responsible for log redirection.
    set +o | grep '+o errexit' && _ereset='set +e' || _ereset='set -e'
    set +e

    if [ ! -e pipeline/sample_summary.yml ] ; then
        #summarize_lane_contents.py --yml pipeline/sample_summary.yml
        #This saves the yml and mails the text in one shot...
        #Subshell needed to capture STDERR from summarize_lane_contents.py
        ( rt_runticket_manager.py -r "$RUNID" --reply \
            @<(summarize_lane_contents.py --yml pipeline/sample_summary.yml --txt -) ) 2>&1
    fi

    # Push any new metadata into the run report.
    # This requires the QC directory to exist, even before demultiplexing starts.
    # In this case, an error in MultiQC etc. should not prevent demultiplexing from starting.
    mkdir -vp "$DEMUX_OUTPUT_FOLDER"/QC |& debug
    # Interop may fail. This is fine.
    ( cd "$DEMUX_OUTPUT_FOLDER" ; Snakefile.qc -- interop_main ) 2>&1
    ( cd "$DEMUX_OUTPUT_FOLDER" ; Snakefile.qc -F -- multiqc_main ) 2>&1

    # Snag that return value
    _retval=$?

    eval "$_ereset"
    return $_retval
}

run_qc() {
    # Hand over to Snakefile.qc for report generation
    # First a quick report. Continue to QC even if MultiQC fails here.
    ( cd "$DEMUX_OUTPUT_FOLDER" && Snakefile.qc -- demux_stats_main interop_main )
    run_multiqc || true

    # Then a full QC. Welldups should have run already but it will not
    # hurt to re-run Snakemake with nothing to do. All these steps must succeed.
    rundir="`pwd`"
    ( cd "$DEMUX_OUTPUT_FOLDER"
      Snakefile.qc -- md5_main qc_main
      Snakefile.welldups --config rundir="$rundir" -- wd_main
    )
    run_multiqc
}

pipeline_fail() {
    stage=${1:-Pipeline}
    # Mark the failure status
    echo "$stage on `date`" > pipeline/failed

    # Send an alert when demultiplexing fails. This always requires attention!
    # Note that after calling 'plog' we can query '$projlog' since all shell vars are global.
    plog "Attempting to notify error to RT"
    if rt_runticket_manager.py -r "$RUNID" --reply "$stage failed. See log in $projlog" |& plog ; then
        log "FAIL $stage $RUNID. See $projlog"
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL $stage $RUNID, and also failed to report the error via RT. See $projlog"
        echo "$msg" >&2
        log "$msg"
    fi
}

log "Looking for run directories matching regex $SEQDATA_LOCATION/$RUN_NAME_REGEX/"

# 6) Scan for each run until we find something that needs dealing with.
for run in "$SEQDATA_LOCATION"/*/ ; do

  # $RUN_NAME_PATTERN is now RUN_NAME_REGEX
  if ! [[ "`basename $run`" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring `basename $run`"
    continue
  fi

  # invoke runinfo and collect some meta-information about the run. We're passing info
  # to the state functions via global variables.
  RUNINFO_OUTPUT="$(RunStatus.py "$run")" || RunStatus.py $run | log 2>&1

  LANES=`grep ^LaneCount: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  STATUS=`grep ^PipelineStatus: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' ' || echo unknown`
  RUNID=`grep ^RunID: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  INSTRUMENT=`grep ^Instrument: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  FLOWCELLID=`grep ^Flowcell: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`

  # FIXME - should probably check that [ "$RUNID" = `basename "$run")` ] or else BAD THINGS (TM)
  # will happen when later bits of the pipeline just assume that it is!

  if [ "$STATUS" = complete ] || [ "$STATUS" = aborted ] ; then _log=debug ; else _log=log ; fi
  $_log "$run has $RUNID from $INSTRUMENT with $LANES lane(s) and status=$STATUS"

  #Call the appropriate function in the appropriate directory.
  BREAK=0
  DEMUX_OUTPUT_FOLDER="$FASTQ_LOCATION/$RUNID"
  { pushd "$run" >/dev/null && eval action_"$STATUS" &&
    popd >/dev/null
  } || log "Error while trying to run action_$STATUS on $run"
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

