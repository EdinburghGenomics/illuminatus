#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

# A driver script that is to be called directly from the CRON.
# It will go through all runs in SEQDATA_LOCATION and take action on them as needed.
# As a well behaved CRON job it should only output critical error messages
# to stdout - this is controlled by the MAINLOG setting.
# The script wants to run every 5 minutes or so, and having multiple instances
# in flight at once is fine, though in fact there are race conditions possible if two
# instances start at once and claim the same run for processing (Snakemake locking
# should catch any fallout before data is scrambled).

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

    # Saves having to put 'export' on every line in the config.
    export CLUSTER_QUEUE FASTQ_LOCATION GENOLOGICSRC PROJECT_NAME_LIST PROJECT_PAGE_URL \
        REDO_HOURS_TO_LOOK_BACK REPORT_DESTINATION REPORT_LINK RT_SYSTEM RUN_NAME_REGEX \
        SEQDATA_LOCATION SSPP_HOOK VERBOSE WRITE_TO_CLARITY
fi

# Tools may reliably use this to report the version of Illuminatus being run right now.
# They should look at pipeline/start_times to see which versions have touched a given run.
export ILLUMINATUS_VERSION=$(cat "$(dirname $BASH_SOURCE)"/version.txt || echo unknown)

LOG_DIR="${LOG_DIR:-${HOME}/illuminatus/logs}"
RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"

BIN_LOCATION="${BIN_LOCATION:-$(dirname $0)}"
PATH="$(readlink -m $BIN_LOCATION):$PATH"
MAINLOG="${MAINLOG:-${LOG_DIR}/bcl2fastq_driver.`date +%Y%m%d`.log}"

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
# at the same time (which we want to be able to do!), so have a plog1 for that.
plog() {
    per_run_log="$DEMUX_OUTPUT_FOLDER/pipeline.log"
    if ! { [ $# = 0 ] && cat >> "$per_run_log" || echo "$*" >> "$per_run_log" ; } ; then
       log '!!'" Failed to write to $per_run_log"
       log "$@"
    fi
}

# Have a special log for the read1 processing, as this can happen in parellel
# with other actions.
plog1() {
    per_run_log1="$DEMUX_OUTPUT_FOLDER/pipeline_read1.log"
    if ! { [ $# = 0 ] && cat >> "$per_run_log1" || echo "$*" >> "$per_run_log1" ; } ; then
       log '!!'" Failed to write to $per_run_log1"
       log "$@"
    fi
}

plog_start() {
    mkdir -vp "$DEMUX_OUTPUT_FOLDER" |& debug
    plog $'>>>\n>>>\n>>>'" $0 starting action_$STATUS at `date`"
}

# Print a message at the top of the log, and trigger one to print at the end.
intro="`date`. Running $(readlink -f "$0"); PID=$$"
log "====`tr -c '' = <<<"$intro"`==="
log "=== $intro ==="
log "====`tr -c '' = <<<"$intro"`==="
trap 'log "=== `date`. Finished run; PID=$$ ==="' EXIT

# We always must activate a Python VEnv, unless explicitly set to 'none'
py_venv="${PY3_VENV:-default}"
if [ "${py_venv}" != none ] ; then
    if [ "${py_venv}" = default ] ; then
        log -n "Running `dirname $BASH_SOURCE`/activate_venv ..."
        pushd "`dirname $BASH_SOURCE`" >/dev/null
        source ./activate_venv || { log 'FAILED' ; exit 1 ; }
        popd >/dev/null
    else
        log -n "Activating Python3 VEnv from ${py_venv} ..."
        reset=`set +o | grep -w nounset` ; set +o nounset
        source "${py_venv}/bin/activate" || { log 'FAILED' ; exit 1 ; }
        $reset
    fi
    log 'VEnv ACTIVATED'
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

save_start_time(){
    ( echo -n "$ILLUMINATUS_VERSION@" ; date +'%a %b %_d %H:%M:%S %Y' ) >>pipeline/start_times
}

action_new(){
    # Create a pipeline/ folder and make a sample sheet summary
    # For now the sample sheet summary will just be a copy of the sample sheet
    # If this works we can BREAK, but if not go on to process more runs

    # In order to run the initial round of MultiQC we'll also end up making the
    # $DEMUX_OUTPUT_FOLDER/QC/ directory. The symlink ./pipeline/output will
    # serve as a shortcut to this, and we'll also have a link in the other direction.
    # We're now sending the logs to the output folder too.
    log "\_NEW $RUNID. Creating ./pipeline folder and making skeleton report."
    set +e ; ( set -e
      mkdir -v ./pipeline |& debug
      mkdir -vp "$DEMUX_OUTPUT_FOLDER" |&debug
      ln -nsv "$DEMUX_OUTPUT_FOLDER" ./pipeline/output |& debug
      ln -nsv "`pwd -P`" ./pipeline/output/seqdata |& debug

      plog_start
      fetch_samplesheet
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
    eval touch pipeline/"lane{1..$LANES}.started"

    log "\_READS_FINISHED $RUNID. Checking for new SampleSheet.csv and preparing to demultiplex."
    plog_start

    # Log the start in a way we can easily read back (humans can check the main log!)
    save_start_time

    # Sort out the SampleSheet and replace with a new one from the LIMS if
    # available.
    fetch_samplesheet
    ( run_multiqc "Reads finished, demultiplexing starting" | plog ) || true

    # Karim wanted an e-mail alert here, with a lane summary.
    # Make sure any printed output is plogged.
    send_summary_to_rt reply demultiplexing "The run finished and demultiplexing will now start. Report is at" |& plog

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
      #' I'm pretty sure RT errors could/should be non-fatal here.
      rt_runticket_manager.py -Q run -r "$RUNID" --subject demultiplexed \
        --comment 'Demultiplexing completed. QC will trigger on next CRON cycle' || true
      log "  Completed bcl2fastq on $RUNID."

    ) |& plog ; [ $? = 0 ] || pipeline_fail Demultiplexing
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
    log "  Now commencing QC on $RUNID."

    # This touch file puts the run into status in_qc.
    # Upload of report is regarded as the final QC step, so if this fails wen need to
    # log a failure.
    touch pipeline/qc.started
    BREAK=1
    set +e ; ( set -e
        run_qc
        log "  Completed QC on $RUNID."

        if [ -s pipeline/report_upload_url.txt ] ; then
            send_summary_to_rt reply "Finished pipeline" \
                "Pipeline completed on $RUNID and QC report is available at"
            # Final success is contingent on the report upload AND that message going to RT.
            mv pipeline/qc.started pipeline/qc.done
        else
            # ||true avoids calling the error handler twice
            pipeline_fail QC_report_final_upload || true
        fi
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
    plog ">>> See pipeline_read1.log for details on read1 processing."
    plog1 </dev/null  #Log1 must be primed before entering subshell!

    # Now is the time for WellDups scanning. Note that we press on despite failure,
    # since we don't want a problem here to hold up demultiplexing.
    # A failure to contact RT is simply ignored
    # There will be a retry at the point of QC with stricter error handling.
    mkdir -vp "$DEMUX_OUTPUT_FOLDER"/QC |& debug
    BREAK=1
    set +e ; ( set +e
        rundir="`pwd`"
        e=''
        cd "$DEMUX_OUTPUT_FOLDER"
        Snakefile.welldups --config rundir="$rundir" -- wd_main || e="$e welldups"
        Snakefile.qc -- interop_main                            || e="$e interop"
        cd "$rundir" ; run_multiqc "Waiting for RTAComplete" NONE "$per_run_log1" || e="$e multiqc"

        if [ -n "$e" ] ; then
            _msg="There were errors in read1 processing (${e# }) on $RUNID. See $per_run_log1"
        else
            _msg="Completed read1 processing on $RUNID."
        fi
        rt_runticket_manager.py -Q run -r "$RUNID" --comment "$_msg" || true
        log "  $_msg"
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
    plog_start

    # Log the start in a way we can easily read back (humans can check the main log!)
    save_start_time

    # Get a list of what needs redoing.
    redo_list=()

    # Remove all .redo files and corresponding .done files
    # Also remove ALL old .started files since once the failed file is gone the
    # system will think these are really running. (Nothing should be running just now!)
    ( rm -f pipeline/lane?.started ) 2>/dev/null || true
    for redo in pipeline/lane?.redo ; do
        stat -c '%n had owner %U' $redo | plog
        touch ${redo%.redo}.started
        rm -f ${redo%.redo}.done ; rm $redo

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
    # Then I can the 'redo lanes ...' subject on the ticket and send a new sample summary as a reply,
    # not a comment.
    # TODO - say what lanes are being demuxed in the final report, since we can't just now promise
    # that all the lanes changed in the sample sheet are the actual ones being re-done. Or a better way
    # might be to detect changes in the sample sheet automatically?
    fetch_samplesheet

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
        Snakefile.demux --config lanes="${redo_list[*]}" rundir="$rundir"
      ) |& plog

      for f in pipeline/lane?.started ; do
          mv $f ${f%.started}.done
      done
      rt_runticket_manager.py -Q run -r "$RUNID" --subject re-demultiplexed \
        --comment "Re-Demultiplexing of lanes ${redo_list[*]} completed" || true
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
    old_ss_link="`readlink -q SampleSheet.csv 2>/dev/null || true`"

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
        _plog="$3" # Caller may hint where the log is going.
    else
        plog </dev/null #Just to set $per_run_log
        _plog="${per_run_log}"
    fi

    # So this will summarize the samples into RT, but at this point there is no
    # link to the report to send to RT. We don't get the link until we do the upload
    # and we can't do the upload til we make the report and we can't make the report
    # without the sample summary. So that's the order we'll do things.
    send_summary=0
    if [ ! -e pipeline/sample_summary.yml ] ; then
        send_summary=1 #Note for later.
        summarize_lane_contents.py --yml pipeline/sample_summary.yml 2>&1
    fi
    _retval=$?

    # Push any new metadata into the run report.
    # This requires the QC directory to exist, even before demultiplexing starts.
    # In this case, an error in MultiQC etc. should not prevent demultiplexing from starting.
    mkdir -vp "$DEMUX_OUTPUT_FOLDER"/QC |& debug
    # Note - running interop here is a problem because if the cluster is busy this will
    # hang until the jobs run. I think it was redundant anyway as read1 and pre-QC trigger it
    # explicitly. What I do need is the metadata.
    ( cd "$DEMUX_OUTPUT_FOLDER" ; Snakefile.qc -- metadata_main ) 2>&1
    ( cd "$DEMUX_OUTPUT_FOLDER" ; Snakefile.qc -F --config pstatus="$_pstatus" -- multiqc_main ) 2>&1

    # Snag that return value
    _retval=$(( $? + $_retval ))

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
    ( set +u ; rt_runticket_manager.py -Q run -r "$RUNID" "${_run_status[@]}" --"${_reply_or_comment}" \
        @<(echo "$_preamble "$'\n'"$last_upload_report" ;
           echo ;
           summarize_lane_contents.py --from_yml pipeline/sample_summary.yml --txt - \
           || echo "Error while summarizing lane contents." ) ) 2>&1
}

run_qc() {
    # At present, this is only ever called by action_demultiplexed.
    # If qc failed, the ticket subject will be 'failed' so reset it (but an RT error should not be fatal).
    rt_runticket_manager.py -Q run -r "$RUNID" --subject in_qc || true

    # Hand over to Snakefile.qc for report generation
    # First a quick report. Continue to QC even if MultiQC fails here.
    ( cd "$DEMUX_OUTPUT_FOLDER" && Snakefile.qc -- demux_stats_main interop_main ) || true
    run_multiqc "In QC" || true

    # Then a full QC. Welldups should have run already but it will not
    # hurt to re-run Snakemake with nothing to do. All these steps must succeed.
    rundir="`pwd`"
    ( cd "$DEMUX_OUTPUT_FOLDER"
      Snakefile.qc -- md5_main qc_main
      Snakefile.welldups --config rundir="$rundir" -- wd_main
    )

    # If we get here, the pipeline completed (or was partially complete) but a failure to
    # upload the final report must still count as a pipeline failure (trapped by the caller)
    run_multiqc "Completed QC"
}

pipeline_fail() {
    stage=${1:-Pipeline}
    # Mark the failure status
    echo "$stage on `date`" > pipeline/failed

    # Send an alert when demultiplexing fails. This always requires attention!
    # Note that after calling 'plog' we can query '$per_run_log' since all shell vars are global.
    plog "Attempting to notify error to RT"
    if rt_runticket_manager.py -Q run -r "$RUNID" --subject failed --reply "$stage failed. See log in $per_run_log" |& plog ; then
        log "FAIL $stage $RUNID. See $per_run_log"
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL $stage $RUNID, and also failed to report the error via RT. See $per_run_log"
        echo "$msg" >&2
        log "$msg"
    fi
}

if [ -n "${REDO_HOURS_TO_LOOK_BACK:-}" ] ; then
    echo "Looking for new replacement sample sheets from the last $REDO_HOURS_TO_LOOK_BACK hours."
    auto_redo.sh
fi

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

  # FIXME - should probably check that [ "$RUNID" = `basename "$run"` ] or else BAD THINGS (TM)
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
wait
