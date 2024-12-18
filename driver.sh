#!/bin/bash
set -euo pipefail
shopt -sq failglob

# A driver script that is to be called directly from the CRON.
# It will go through all runs in SEQDATA_LOCATION and take action on them as needed.
# As a well behaved CRON job it should only output critical error messages
# to stdout - this is controlled by the MAINLOG setting.
# The script wants to run every 5 minutes or so, and having multiple instances
# in flight at once is fine, though theoretically are race conditions possible if two
# instances start at once and claim the same run for processing (but that will be caught
# by touch_atomic so in the worst case you should just get an error).

# Note within this script I've tried to use ( subshell blocks ) along with "set -e"
# to emulate eval{} statements in Perl. It does work but you have to be really careful
# on the syntax, and you have to check $? explicitly - trying to do it implicitly in
# the manner of ( foo ) || handle_error won't do what you expect (and the behaviour
# changes in different BASH versions!)

# Canonicalize the path.
BASH_SRC="$(readlink -f "$BASH_SOURCE")"
BASH_DIR="$(dirname "$BASH_SRC")"

# For the sake of the unit tests, we must be able to skip loading the config file,
# so allow the location to be set to, eg. /dev/null
ENVIRON_SH="${ENVIRON_SH:-$BASH_DIR/environ.sh}"

# This file must provide SEQDATA_LOCATION, FASTQ_LOCATION if not set externally.
if [ -e "$ENVIRON_SH" ] ; then
    pushd "`dirname $ENVIRON_SH`" >/dev/null
    source "`basename $ENVIRON_SH`"
    popd >/dev/null

    # Saves having to put 'export' on every line in the config.
    export SEQDATA_LOCATION    FASTQ_LOCATION    GENOLOGICSRC  SAMPLESHEETS_ROOT \
           RT_SYSTEM           PROJECT_PAGE_URL  \
           REPORT_DESTINATION  REPORT_LINK       REPORT_RSYNC     \
           RUN_NAME_REGEX      PROJECT_NAME_LIST \
           CLUSTER_PARTITION   EXTRA_SLURM_FLAGS \
           SSPP_HOOK           TOOLBOX           VERBOSE \
           WRITE_TO_CLARITY    DRY_RUN           \
           SNAKE_THREADS       LOCAL_CORES       EXTRA_SNAKE_FLAGS \
           REDO_HOURS_TO_LOOK_BACK
fi

# Just because I renamed it
if [ -n "${RSYNC_CMD:-}" ] && [ -z "${REPORT_RSYNC:-}" ] ; then
    echo 'RSYNC_CMD option is now REPORT_RSYNC. Please fix your config.'
    exit 1
fi

# FIXME - DRY_RUN should actually activate a dry run, rather than being ignored.
if [ "${DRY_RUN:-0}" = 1 ] ; then
    echo "DRY_RUN mode is not yet supported :-("
    exit 1
fi

# Set HOSTNAME if we don't have it already
export HOSTNAME="${HOSTNAME:-$(hostname -s)}"

LOG_DIR="${LOG_DIR:-${HOME}/illuminatus/logs}"
RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"

BIN_LOCATION="${BIN_LOCATION:-$BASH_DIR}"
MAINLOG="${MAINLOG:-${LOG_DIR}/illuminatus_driver.$(date +%Y%m%d).log}"

# 1) Sanity check these directories exist and complain to STDERR (triggering CRON
#    warning mail) if not.
for d in "${BIN_LOCATION%%:*}" "$SEQDATA_LOCATION" "$FASTQ_LOCATION" ; do
    if ! [ -d "$d" ] ; then
        echo "No such directory '$d'" >&2
        exit 1
    fi
done

# 2) Ensure that the directory is there for the main log file and set up logging
#    on file descriptor 5.
if [ "$MAINLOG" = '/dev/stdout' ] ; then
    exec 5>&1
elif [ "$MAINLOG" = '/dev/stderr' ] ; then
    exec 5>&2
else
    mkdir -p "$(dirname "$MAINLOG")" ; exec 5>>"$MAINLOG"
fi

# Main log for general messages (STDERR still goes to the CRON).
log(){ [ $# = 0 ] && cat >&5 || echo "$@" >&5 ; }

# Debug means log only if VERBOSE is set
debug(){ if [ "${VERBOSE:-0}" != 0 ] ; then log "$@" ; else [ $# = 0 ] && cat >/dev/null || true ; fi ; }

# Per-run log for run progress messages, goes into the output # directory.
# Unfortunately this could get scrambled if we try to run read1 processing and demux
# at the same time (which we want to be able to do!), so have a p|& debug log1 for that.
plog() {
    per_run_log="$(readlink -f ./pipeline/output)/pipeline.log"
    if ! { [ $# = 0 ] && cat >> "$per_run_log" || echo "$*" >> "$per_run_log" ; } 2>/dev/null ; then
       log '!!'" Failed to write to $per_run_log:"
       log "$@"
    fi
}

# Have a special log for the read1 processing, as this can happen in parellel
# with other actions.
plog1() {
    per_run_log1="$(readlink -f ./pipeline/output)/pipeline_read1.log"
    if ! { [ $# = 0 ] && cat >> "$per_run_log1" || echo "$*" >> "$per_run_log1" ; } ; then
       log '!!'" Failed to write to $per_run_log1"
       log "$@"
    fi
}

plog_start() {
    plog $'>>>\n>>>\n>>>'" $BASH_SRC starting action_$STATUS at $(date)"
}

# Print a message at the top of the log, and trigger one to print at the end.
intro="$(date). Running $BASH_SRC; PID=$$"
log "====$(tr -c '' = <<<"$intro")==="
log "=== $intro ==="
log "====$(tr -c '' = <<<"$intro")==="
trap 'log "=== $(date). Finished run; PID=$$ ==="' EXIT

# We always must activate a Python VEnv, unless explicitly set to 'none'
# Do this before other PATH manipulations.
py_venv="${PY3_VENV:-default}"
if [ "${py_venv}" != none ] ; then
    if [ "${py_venv}" = default ] ; then
        log -n "Running $BASH_DIR/activate_venv ..."
        pushd "$BASH_DIR" >/dev/null
        source ./activate_venv >&5 || { log 'FAILED' ; exit 1 ; }
        popd >/dev/null
    else
        log -n "Activating Python3 VEnv from ${py_venv} ..."
        reset=`set +o | grep -w nounset` ; set +o nounset
        source "${py_venv}/bin/activate" >&5 || { log 'FAILED' ; exit 1 ; }
        $reset
    fi
    log 'VEnv ACTIVATED'
fi

# Fix the PATH only after VEnv activation
PATH="$(readlink -m "$BIN_LOCATION"):$PATH"

# Tools may reliably use this to report the version of Illuminatus being run right now.
# They should look at pipeline/start_times to see which versions have touched a given run.
# Note we don't run this until after VEnv activation so we can't print this version at
# the top of the log.
export ILLUMINATUS_VERSION=$(illuminatus_version.py)


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

save_start_time(){
    # We log each time the pipeline starts. This is where we look to see which
    # version(s) of the pipeline processed a run.
    echo "${ILLUMINATUS_VERSION}@$(date +%s)" >>pipeline/start_times
}

rt_runticket_manager(){
    # Simple wrapper for ticket manager that sets the run and queue
    rt_runticket_manager.py -Q run -r "$RUNID" "$@"
}

action_new(){
    # Create an output directory for the new run. Being conservative, if this
    # already exists then fail.

    # Also create a pipeline/ directory and make a sample sheet summary
    # For now the sample sheet summary will just be a copy of the sample sheet
    # If this works we can BREAK, but if not go on to process more runs

    # In order to run the initial round of MultiQC we'll also end up making the
    # $DEMUX_OUTPUT_FOLDER/QC/ directory. The symlink ./pipeline/output will
    # serve as a shortcut to this, and we'll also have a link in the other direction.
    # We're now sending the logs to the output dir too.

    # And as of version 1.4, we set the group ownership on the pipeline dir to
    # be the same as the output dir.
    log "\_NEW $RUNID. Creating ./pipeline folder and making skeleton report."
    set +e ; ( set -e
      mkdir ${VERBOSE:+-v} ./pipeline |& log
      mkdir ${VERBOSE:+-v} "$DEMUX_OUTPUT_FOLDER" |& log
      ln ${VERBOSE:+-v} -ns "$DEMUX_OUTPUT_FOLDER" ./pipeline/output |& log
      ln ${VERBOSE:+-v} -ns "`pwd -P`" ./pipeline/output/seqdata |& log
      chgrp ${VERBOSE:+-c} --reference="$DEMUX_OUTPUT_FOLDER" ./pipeline |& log

      plog_start
      fetch_samplesheet |& plog
    ) ; [ $? = 0 ] && BREAK=1 || { pipeline_fail Scan_new_run ; return ; }

    # Run an initial report but don't abort the pipeline if this fails - the error
    # will be noted by the main loop.
    # If necessary, Snakefile.qc and upload_report.sh could be run manually
    # to get the skeleton report.
    run_multiqc "Waiting for data" "new" | plog && log DONE
}

action_reads_unfinished(){
    log "\_READS_UNFINISHED $RUNID. Waiting for data."
}

action_reads_finished(){
    # Lock the run by writing pipeline/lane?.started per lane
    # Note this action must not attempt to run any QC ops - an interim report will be triggered
    # by action_demultiplexed before it fires off all the QC jobs.
    log "\_READS_FINISHED $RUNID. Checking for new SampleSheet.csv and preparing to demultiplex."
    check_outdir || return 0
    eval touch_atomic pipeline/"lane{1..$LANES}.started"
    plog_start

    # Log the start in a way we can easily read back (humans can check the main log!)
    save_start_time

    # Sort out the SampleSheet and replace with a new one from the LIMS if
    # available.
    fetch_samplesheet |& plog
    summarize_lane_contents.py --yml pipeline/sample_summary.yml |& plog

    # We used to run MultiQC here, before running bcl2fastq, but I think with the expanded read1
    # processing this is redundant. But we do still want the alert to be sent to RT.
    ( send_summary_to_rt reply demultiplexing \
                         "The run finished and demultiplexing will now start. Report will appear at" || true
    ) |& plog

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
        Snakefile.demux --config lanes="$(quote_lanes `seq $LANES`)" rundir="$rundir"
      ) |& plog

      for f in pipeline/lane?.started ; do
          # Changed from 'mv' to fix the timestamp
          mv_atomic $f ${f%.started}.done
      done
      #' I'm pretty sure RT errors could/should be non-fatal here.
      rt_runticket_manager --subject demultiplexed \
        --comment 'Demultiplexing completed. QC will trigger on next CRON cycle' || true
      log "  Completed bcl2fastq on $RUNID."

    ) |& plog ; [ $? = 0 ] || { pipeline_fail Demultiplexing ; return ; }
}

action_in_read1_qc_reads_finished(){
    #Same as above
    debug "\_IN_READ1_QC_READS_FINISHED $RUNID"

    action_reads_finished
}

# What about the transition from demultiplexing to QC? Do we need a new status,
# or is the QC part just hooked off the back of BCL2FASTQ?
# I say the former, or else it is harder to re-run QC without re-demultiplexing,
# and also to see exactly where the run is. (See state diagram)
action_demultiplexed() {
    log "\_DEMULTIPLEXED $RUNID"

    # This touch file puts the run into status in_qc.
    # Upload of report is regarded as the final QC step, so if this fails we need to
    # log a failure.
    touch_atomic pipeline/qc.started
    check_outdir || return 0
    log "  Now commencing QC on $RUNID."
    BREAK=1

    set +e

    # In certain cases read1_qc can make a 1-tile report with a later timestamp than the full
    # bcl2fastq output and the reduced numbers end up in the final report. To be sure, touch all
    # the real Stats.json files so Snakemake sees they are new and picks them up.
    ( cd "$DEMUX_OUTPUT_FOLDER"/demultiplexing && \
      touch lane*/Stats/Stats.json
    ) |& plog ; [ $? = 0 ] || { pipeline_fail Touch_Stats_json ; return ; }

    ( set -e
      run_qc
      log "  Completed QC on $RUNID."
    ) |& plog ; [ $? = 0 ] || { pipeline_fail QC ; return ; }

    if [ -s pipeline/report_upload_url.txt ] ; then
        ( set -e
          send_summary_to_rt reply "Finished pipeline" \
              "Complete QC report available at"
        ) |& plog ; [ $? = 0 ] || { pipeline_fail RT_final_message ; return ; }
        # Final success is contingent on the report upload AND that message going to RT.
        plog "pipeline/qc.started -> pipeline/qc.done"
        mv_atomic pipeline/qc.started pipeline/qc.done |& plog
    else
        debug "pipeline/report_upload_url.txt is missing or empty"
        # ||true avoids calling the error handler twice
        pipeline_fail QC_report_final_upload || true
    fi

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
    touch_atomic pipeline/read1.started
    check_outdir || return 0
    log "  Now commencing read1 processing on $RUNID."

    plog_start
    plog ">>> See pipeline_read1.log for details on read1 processing."
    plog1 </dev/null  #Log1 must be primed before entering subshell!

    # Re-fetch the sample sheet since we're going to do a demultiplex.
    fetch_samplesheet |& plog1

    # Set up a message to be passed to the "-b" option of MultiQC because the numbers
    # on the reports are for one tile only.
    mqc_comment="A single tile was demultiplexed to check the barcodes. Await the final report for true numbers."

    # Now is the time for WellDups scanning. Note that we press on despite failure,
    # since we don't want a problem here to hold up demultiplexing.
    # A failure to contact RT is simply ignored
    # There will be a retry at the point of QC with stricter error handling.
    mkdir -vp "$DEMUX_OUTPUT_FOLDER"/QC |& debug
    BREAK=1
    set +e ; ( set +e
        e=''
        pushd "$DEMUX_OUTPUT_FOLDER"
        rm -f "QC/bc_check/bc_check.msg"
        if ! Snakefile.read1qc -- wd_main bc_main ; then
          # Retry and log specific failure
          Snakefile.read1qc -- bc_main  || e="$e bc_check"
          Snakefile.read1qc -- wd_main  || e="$e welldups"
        fi
        Snakefile.qc -- interop_main    || e="$e interop"
        popd
        run_multiqc "Waiting for RTAComplete" NONE "$per_run_log1" "$mqc_comment" || e="$e multiqc"

        if [ -n "$e" ] ; then
            _msg="There were errors in read1 processing (${e# }) on $RUNID. See $per_run_log1"
        else
            _msg="Completed read1 processing on $RUNID."
        fi

        # Did bc_check produce any alert, or should we just log the usual comment?
        if [ -s "$DEMUX_OUTPUT_FOLDER/QC/bc_check/bc_check.msg" ] ; then
            _full_msg="$_msg"$'\n\n'"$(cat "$DEMUX_OUTPUT_FOLDER/QC/bc_check/bc_check.msg")"
            log '  Barcode check does not look good! Reporting to RT.'
            echo $'Barcode problem...\n>>>\n'"$_full_msg"$'\n<<<'
            send_summary_to_rt reply "barcode problem" \
                "$_full_msg"$'\n'"Report is at"
        else
            rt_runticket_manager --comment "$_msg" || true
        fi
        log "  $_msg"
    ) |& plog1

    # We're done. If the above block was interrupted by SIGINT we'll arrive here
    # with $? set to 130. Log the interruption but still set the done flag as the state
    # diagram demands it.
    if [ "$?" != 0 ] ; then
        plog1 "Interrupted during read1 processing on $RUNID."
        log "  Interrupted during read1 processing on $RUNID."
    fi

    mv_atomic pipeline/read1.started pipeline/read1.done |& plog1
}

action_in_read1_qc() {
    debug "\_IN_READ1_QC $RUNID"
}

action_in_qc() {
    debug "\_IN_QC $RUNID"
}

action_failed() {
    # failed runs need attention, but for now just log the situation
    log "\_FAILED $RUNID (`cat pipeline/failed`)"
}

action_aborted() {
    # aborted runs are always ignored
    true
}

action_complete() {
    # the pipeline already fully completed for this run ... nothing to be done
    true
}

action_redo() {
    # Some lanes need to be re-done. Complicated...
    log "\_REDO $RUNID"
    check_outdir || return 0
    plog_start

    # Log the start in a way we can easily read back (humans can check the main log!)
    save_start_time

    # Get a list of what needs redoing.
    redo_list=()

    # Remove all .redo files and corresponding .done files
    # Also remove ALL old .started files since once the failed file is gone the
    # system will think these are really running. (Nothing should be running just now!)
    # And touch read1.done to ensure we don't [re-]do the read1 processing
    ( rm -f pipeline/lane?.started ) 2>/dev/null || true
    for redo in pipeline/lane?.redo ; do
        stat -c '%n had owner %U' $redo | plog
        touch_atomic ${redo%.redo}.started
        rm -f ${redo%.redo}.done ; rm $redo
        touch_atomic pipeline/read1.done |& plog || true

        [[ "$redo" =~ .*(.)\.redo ]]
        redo_list+=(${BASH_REMATCH[1]})
    done
    # Clean out all the other flags, and the sample summary
    rm -f pipeline/{qc.started,qc.done,failed,aborted,sample_summary.yml}

    BREAK=1  # If we fail after this, don't try to process more runs on this cycle.

    # Fetch and re-summarize the sample sheet, as it presumably changed, and I've deleted sample_summary.yml
    # in any case.
    # Calling run_multiqc will make the new summary but I suppress the RT comment as it will be redundant.
    # I need to clean out the actual data before running multiqc so that the interim report will not contain
    # the stale results.
    # Then I can add the 'redo lanes ...' subject on the ticket and send a new sample summary as a reply,
    # not a comment.
    set +e ; ( set -e
        fetch_samplesheet
    ) |& plog ; [ $? = 0 ] || { pipeline_fail Fetch_Sample_Sheet ; return ; }

    set +e ; ( set -e
      if [ -e "$DEMUX_OUTPUT_FOLDER" ] ; then
        BCL2FASTQCleanup.py "$DEMUX_OUTPUT_FOLDER" "${redo_list[@]}"
      fi
    ) |& plog ; [ $? = 0 ] || { pipeline_fail Cleanup_for_Re-demultiplexing ; return ; }

    run_multiqc "Re-demultiplexing lanes ${redo_list[*]}" NONE | plog
    send_summary_to_rt reply "redo lanes ${redo_list[*]}" \
        "Re-Demultiplexing of lanes ${redo_list[*]} was requested. Updated report will appear at" |& plog

    set +e ; ( set -e
      mkdir -vp "$DEMUX_OUTPUT_FOLDER"/demultiplexing

      log "  Starting bcl2fastq on $RUNID lanes ${redo_list[*]}."
      ( rundir="`pwd`"
        cd "$DEMUX_OUTPUT_FOLDER"/demultiplexing
        Snakefile.demux --config lanes="$(quote_lanes ${redo_list[*]})" rundir="$rundir"
      ) |& plog

      for f in pipeline/lane?.started ; do
          mv_atomic $f ${f%.started}.done
      done
      rt_runticket_manager --subject re-demultiplexed \
        --comment "Re-Demultiplexing of lanes ${redo_list[*]} completed" || true
      log "  Completed demultiplexing on $RUNID lanes ${redo_list[*]}."

    ) |& plog ; [ $? = 0 ] || { pipeline_fail Re-demultiplexing ; return ; }

}

action_unknown() {
    # this run either has no RunInfo.xml or an invalid set of touch files ... nothing to be done...
    log "\_skipping `pwd` because status is $STATUS"
}

### Other utility functions used by the actions.
touch_atomic(){
    # Create a file or files but it's an error if the file already existed.
    for f in "$@" ; do
        (set -o noclobber ; >"$f")
    done
}

mv_atomic(){
    # Used in place of "mv x.started x.done"
    echo "renaming $1 -> $2"
    (set -o noclobber ; >"$2") && rm "$1"
}

check_outdir(){
    # Ensure that pipeline/output is a directory, and fail in a sensible way if it is not.
    # Caller may override the failure reason.
    if [ -d pipeline/output ] ; then
        return 0
    fi
    log "ERROR ./pipeline/output directory is missing or invalid"

    # Modified version of pipeline_fail()
    stage="${1:-Missing_Output_Dir}"
    echo "$stage on $(date)" > pipeline/failed

    # Send an alert to RT but obviously we can't plog anything.
    log "Attempting to notify error to RT"
    if rt_runticket_manager --subject failed --reply "Processing failed. $stage. See log in $MAINLOG" |& log ; then
        log "FAIL $stage $RUNID."
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL $stage $RUNID, and also failed to report the error via RT. See $MAINLOG"
        echo "$msg" >&2
        log "$msg"
    fi
    return 1
}

quote_lanes(){
    # Given a list of lane numbers, eg. "1 2 4 6"
    # Returns "[1,2,4,6]" which will keep Snakemake happy.
    echo "[$(tr ' ' ',' <<<"$*")]"
}

fetch_samplesheet(){
    # Tries to fetch an updated samplesheet. If this is the first run, or if
    # a new one was found, delete the stale sample_summary.yml.
    old_ss_link="`readlink -q SampleSheet.csv 2>/dev/null || true`"

    # Currently if samplesheet_fetch.sh returns an error the pipeline generally aborts, as
    # this indicates a fundamental problem.
    samplesheet_fetch.sh
    new_ss_link="`readlink -q SampleSheet.csv || true`"

    if [ "$old_ss_link" != "$new_ss_link" ] ; then
        rm -vf pipeline/sample_summary.yml
    fi

    # In any case, ensure we know what all the projects in the sample sheet
    # are called.
    project_real_names.py --sample_sheet SampleSheet.csv \
                          --yaml pipeline/project_names.yaml \
                          --update || true
}

run_multiqc() {
    # Runs multiqc. Will not exit on error.
    # usage: run_multiqc [report_status] [rt_run_status] [plog_dest]
    # A blank rt_run_status will leave the status unchanged. A value of "NONE" will
    # suppress reporting to RT entirely.
    # Caller is responsible for log redirection, so this function just prints any
    # progress messages, but the [plog_dest] hint can be used to ensure the right
    # file is referenced when logging error messages.
    set +o | grep '+o errexit' && _ereset='set +e' || _ereset='set -e'
    set +e

    _pstatus="${1:-}"
    _rt_run_status="${2:-}"

    if [ "${3:--}" != - ] ; then
        _plog="$3" # Caller may hint where the log is going - ie. for read1.log
    else
        plog </dev/null #Just to set $per_run_log
        _plog="${per_run_log}"
    fi

    _mqc_comment="${4:-[]}"

    # So this will summarize the samples into RT, but at this point there is no
    # link to the report to send to RT. We don't get the link until we do the upload
    # and we can't do the upload til we make the report and we can't make the report
    # without the sample summary. So that's the order we'll do things.
    send_summary=0
    if [ ! -e pipeline/sample_summary.yml ] ; then
        send_summary=1 #Note for later.
    fi
    summarize_lane_contents.py --yml pipeline/sample_summary.yml 2>&1
    _retval=$?

    # Push any new metadata into the run report.
    # This requires the QC directory to exist, even before demultiplexing starts.
    # In this case, an error in MultiQC etc. should not prevent demultiplexing from starting.
    mkdir -vp "$DEMUX_OUTPUT_FOLDER"/QC |& debug
    # Note - running interop here is a problem because if the cluster is busy this will
    # hang until the jobs run. I think it would be redundant anyway as read1 and pre-QC trigger it
    # explicitly. What I do need is the metadata.
    if ( cd "$DEMUX_OUTPUT_FOLDER" ; Snakefile.qc -- metadata_main ) 2>&1 ; then
        ( cd "$DEMUX_OUTPUT_FOLDER" ;
          Snakefile.qc -F --config pstatus="$_pstatus" comment="$_mqc_comment" -- multiqc_main ) 2>&1

        # Snag that return value
        _retval=$(( $? + $_retval ))
    else
        _retval=1
    fi

    # Push to server and capture the result (if upload_report.sh does not error it must print a URL)
    # We want stderr from upload_report.sh to go to stdout, so it gets plogged.
    # Note that the code relies on checking the existence of this file to see if the upload worked,
    # so if the upload fails it needs to be removed.
    rm -f pipeline/report_upload_url.txt
    if [ $_retval = 0 ] ; then
        upload_report.sh "$DEMUX_OUTPUT_FOLDER" 2>&1 >pipeline/report_upload_url.txt || \
            { log "Upload error. See $_plog" ;
              rm -f pipeline/report_upload_url.txt ; }
    fi

    if [ "$send_summary" = 1 ] && [ "$_rt_run_status" != NONE ] ; then
        # A new summary was made so we need to send it.
        # This has now been demoted to a comment, but for a brand new ticket this will still
        # trigger an e-mail with the summary which is what we want.
        send_summary_to_rt comment "$_rt_run_status"
    fi

    # If this fails, the pipeline will continue, since only the final message to RT
    # is seen as critical. We used to remove pipeline/sample_summary.yml to trigger a new
    # report but since this is now sent with every message there's no need.
    if [ $? != 0 ] ; then
        _retval=$(( $_retval + 1 ))
    fi

    # Tell Clarity the proper name for this run. Needs to be done at least before the second report
    # is uploaded so we may as well do it every time. But there is no need to hang around while it runs.
    if [ "${WRITE_TO_CLARITY:-no}" = yes ] ; then
        echo "Running: clarity_run_id_setter.py $RUNID (asynchronously)"
        clarity_run_id_setter.py -- "$RUNID" 2>&1 &
    fi

    # Leaving this in due to unresolved unexpected behaviour after RT timeout.
    echo "driver.sh::run_multiqc() is returning with $_retval"

    eval "$_ereset"
    # Retval will be >1 if anything failed. It's up to the caller what to do with this info.
    # The exception is for the upload. Caller should check for the URL file to see if that that failed.
    return $_retval
}

send_summary_to_rt() {
    # Sends a summary to RT. It is assumed that pipeline/report_upload_url.txt and pipeline/sample_summary.yml
    # are in place and can be read.
    # Other than that, supply run_status and premble if you want this.
    # This function will return the return value from rt_runticket_manager.py
    _reply_or_comment="${1:-}"
    _run_status="${2:-}"
    _preamble="${3:-Run report is at}"

    # Quoting of a subject with spaces requires use of arrays but beware this:
    # https://stackoverflow.com/questions/7577052/bash-empty-array-expansion-with-set-u
    if [ -n "$_run_status" ] ; then
        _run_status=(--subject "$_run_status")
    else
        _run_status=()
    fi

    echo "Sending new summary of run contents to RT."
    # Subshell needed to capture STDERR from summarize_lane_contents.py
    last_upload_report="`cat pipeline/report_upload_url.txt 2>/dev/null || echo "Report was not generated or upload failed"`"
    ( set +u ; rt_runticket_manager "${_run_status[@]}" --"${_reply_or_comment}" \
        @<(echo "$_preamble "$'\n'"$last_upload_report" ;
           echo ;
           summarize_lane_contents.py --from_yml pipeline/sample_summary.yml --txt - \
           || echo "Error while summarizing lane contents." ) ) 2>&1
}

run_qc() {
    # At present, this is only ever called by action_demultiplexed.
    # If qc failed, the ticket subject will be 'failed' so reset it (but an RT error should not be fatal).
    rt_runticket_manager --subject in_qc || true

    # Hand over to Snakefile.qc for report generation
    # First a quick report. Continue to QC even if MultiQC fails here.
    ( cd "$DEMUX_OUTPUT_FOLDER" && \
      Snakefile.qc -- demux_stats_main interop_main
    ) || true
    run_multiqc "In QC" || true

    # Then a full QC. Welldups should have run already but it will not
    # hurt to re-run Snakemake with nothing to do. All these steps must succeed.
    ( cd "$DEMUX_OUTPUT_FOLDER"
      Snakefile.qc -- md5_main qc_main
      Snakefile.read1qc -- wd_main
    )

    # If we get here, the pipeline completed (or was partially complete) but a failure to
    # generate or upload the final report must still count as a pipeline failure, so allow
    # any error from run_multiqc to propogate.
    debug "run_multiqc 'Completed QC' at $0 line $LINENO"
    run_multiqc "Completed QC"
}

pipeline_fail() {
    stage=${1:-Pipeline}
    # Mark the failure status
    echo "$stage on $(date)" > pipeline/failed

    # Send an alert when demultiplexing fails. This always requires attention!
    # Note that after calling 'plog' we can query '$per_run_log' since all shell vars are global.
    plog "Attempting to notify error to RT"
    if rt_runticket_manager --subject failed --reply "$stage failed. See log in $per_run_log" |& plog ; then
        log "FAIL $stage $RUNID. See $per_run_log"
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL $stage $RUNID, and also failed to report the error via RT. See $per_run_log"
        echo "$msg" >&2
        log "$msg"
    fi
}

get_run_status() { # run_dir
  # invoke RunStatus.py in CWD and collect some meta-information about the run.
  # We're passing this info to the state functions via global variables.
  _run="$1"

  # This construct allows error output to be seen in the log.
  _runstatus="$(RunStatus.py "$_run")" || RunStatus.py "$_run" | log 2>&1

  # Capture the various parts into variables (see test/grs.sh in Hesiod)
  for _v in RUNID/RunID INSTRUMENT/Instrument STATUS/PipelineStatus \
            LANES/LaneCount FLOWCELLID/Flowcell ; do
    _line="$(awk -v FS=":" -v f="${_v#*/}" '$1==f {gsub(/^[^:]*:[[:space:]]*/,"");print}' <<<"$_runstatus")"
    eval "${_v%/*}"='"$_line"'
  done

  if [ -z "${STATUS:-}" ] ; then
    STATUS=unknown
  fi

  # Resolve output location (this has to work for new runs so we can't always follow the symlink)
  if [ -d "$_run/pipeline/output" ] ; then
    DEMUX_OUTPUT_FOLDER="$(readlink -f "$_run/pipeline/output")"
  else
    DEMUX_OUTPUT_FOLDER="$FASTQ_LOCATION/$RUNID"
  fi
}

# **** And now the main processing actions, starting with a search for updated sample sheets for
# **** previously processed runs.

if [ -n "${REDO_HOURS_TO_LOOK_BACK:-}" ] ; then
    log "Looking for new replacement sample sheets from the last $REDO_HOURS_TO_LOOK_BACK hours."
    auto_redo.sh |& log || true
fi

log "Looking for run directories matching regex $SEQDATA_LOCATION/$RUN_NAME_REGEX/"

# 6) Scan for each run until we find something that needs dealing with.
for run in "$SEQDATA_LOCATION"/*/ ; do

  # $RUN_NAME_PATTERN is now RUN_NAME_REGEX
  if ! [[ "`basename $run`" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring `basename "$run"`"
    continue
  fi

  # invoke runinfo and collect some meta-information about the run. We're passing info
  # to the state functions via global variables: RUNID LANES FLOWCELLID etc.
  get_run_status "$run"

  # Check that [ "$RUNID" = `basename "$run"` ] or else BAD THINGS (TM)
  # will happen when later bits of the pipeline just assume that it is!
  if [ "$RUNID" != `basename "$run"` ] ; then
    log "Error processing $run. The RunInfo.xml says the run is named $RUNID. Names must match."
    continue
  fi

  if [ "$STATUS" = complete ] || [ "$STATUS" = aborted ] ; then _log=debug ; else _log=log ; fi
  $_log "$run has $RUNID from $INSTRUMENT with $LANES lane(s) and status=$STATUS"

  #Call the appropriate function in the appropriate directory.
  BREAK=0
  pushd "$run" >/dev/null ; eval action_"$STATUS"
  # Even though 'set -e' is in effect this next line is reachable if the called function turns
  # it off...
  [ $? = 0 ] || log "Error while trying to run action_$STATUS on $run"
  # Reset the error trap in any case
  set -e
  popd >/dev/null

  # If the driver started some actual work it should request to break, as the CRON will start
  # a new scan at regular intervals in any case. We don't want an instance of the driver to
  # spend 2 hours demultiplexing then start working on a new run. On the other hand, we don't
  # want a problem run to gum up the pipeline if every instance of the script tries to process
  # it, fails, and then exits.
  # Negated test is needed to play nicely with 'set -e'
  ! [ "$BREAK" = 1 ] || break
done
wait
