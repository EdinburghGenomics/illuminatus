#!/bin/bash
set -euo pipefail
shopt -s nullglob

# Optional echo
debug(){ if [ "${VERBOSE:-0}" != 0 ] ; then echo "$@" ; fi ; }

# Load the settings for this pipeline.
ILLUMINATUS_HOME="$(readlink -f $(dirname $BASH_SOURCE)/..)"
ENVIRON_SH="${ENVIRON_SH:-$ILLUMINATUS_HOME/environ.sh}"
if [ -e "$ENVIRON_SH" ] ; then
    pushd "`dirname $ENVIRON_SH`" >/dev/null
    source "`basename $ENVIRON_SH`"
    popd >/dev/null

    export FASTQ_LOCATION RT_SYSTEM RUN_NAME_REGEX \
        SEQDATA_LOCATION VERBOSE BACKUP_LOCATION BACKUP_NAME_REGEX
fi

# Add the PATH
export PATH="$ILLUMINATUS_HOME:$PATH"

# This file must provide FASTQ_LOCATION and BACKUP_LOCATION, assuming they
# were not already set in the environment. To explicitly ignore the environ.sh
# do something like:
# $ env ENVIRON_SH=/dev/null FASTQ_LOCATION=foo BACKUP_LOCATION=bar sync_to_fluidfs.sh

# Where are runs coming from?
# Where are runs going to (can be a local directory or host:/path)?
echo "Backing up data from $FASTQ_LOCATION to $BACKUP_LOCATION"

# We can supply a BACKUP_NAME_REGEX or fall back to RUN_NAME_REGEX (the default here
# should match the one hard-coded in driver.sh)
RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"
RUN_NAME_REGEX="${BACKUP_NAME_REGEX:-$RUN_NAME_REGEX}"
debug "RUN_NAME_REGEX=$RUN_NAME_REGEX"
echo ===

# Now loop through all the projects in a similar manner to the driver and the state reporter.
# But note we loop through $FASTQDATA_LOCATION not $SEQDATA_LOCATION.
for run in "$FASTQ_LOCATION"/*/ ; do

  # This also lops the trailing /, but we rely on $run still having one.
  run_name="`basename $run`"

  # Apply filter
  if ! [[ "$run_name" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring directory $run_name which does not match regex"
    continue
  fi

  # Invoke RunStatus.py -q to quickly see if the run is done.
  # Actually, no, I'll do a quicker and dirtier way.
  #  RUNINFO_OUTPUT="$(RunStatus.py -q "$run")"
  #  STATUS=`grep ^PipelineStatus: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' ' || echo unknown`
  if [ -e "$run/seqdata/pipeline/aborted" ] ; then
    debug "Ignoring aborted $run_name"
    continue
  fi

  # Wait for qc.done before running the sync.
  # Maybe I should RSYNC anyway here and not wait for final QC? But that gets messy.
  # If the pipeline dir is missing this check will be skipped, but we do need the log - see the next check.
  if [ -e "$run/seqdata/pipeline" ] && [ ! -e "$run/seqdata/pipeline/qc.done" ] ; then
    echo "Ignoring incomplete $run_name"
    continue
  fi

  # If the pipeline.log is missing we have problems
  if [ ! -e "$run/pipeline.log" ] ; then
    echo "Missing $run/pipeline.log - something is wrong here! Run will not be copied!"
    continue
  fi

  # Comparing times on pipeline.log is probably the simplest way to see if the copy
  # is up-to-date and saves my sync-ing everything again and again
  # Note this will also trigger if the run directory itself has changed (perms or mtime)
  if rsync -ns -rlptgD --itemize-changes --include='pipeline.log' --exclude='*' "$run" "$BACKUP_LOCATION/$run_name" | grep -q . ; then
    log_size=`stat -c %s "$run/pipeline.log"`
    echo "Detected activity for $run_name with log size $log_size"
  else
    debug "No recent pipeline activity for $run_name"
    continue
  fi

  # === OK, here we go with the actual sync... ===
  echo "*** Starting sync for $run_name ***"

  if [ "${BACKUP_DRY_RUN:-0}" != 0 ] ; then
    echo "*** DRY_RUN - skipping ***"
    continue
  fi

  if [ "${VERBOSE:-0}" != 0 ] ; then set -x ; fi

  # Note there is no --delete flag so if the sample list changes the old files will remain on the backup.
  # This should not be a problem. If --delete is added below then the --backup flag should prevent cascading data
  # loss in the case where files are accidentally removed from the master copy.
  # Since --backup implies --omit-dir-times we have to do a special fix for that, or else the test for activity gets
  # triggered again and again.
  rsync -sbav --exclude='**/.snakemake' --exclude='**/slurm_output' --exclude={seqdata,projects_deleted.txt,pipeline.log} \
    "$run" "$BACKUP_LOCATION/$run_name"
  rsync -svrtg --exclude='**' \
    "$run" "$BACKUP_LOCATION/$run_name"

  # Just to test the log catcher below we can...
  # echo BUMP >> "$run/pipeline.log"

  # Now add the pipeline directory and the SampleSheets from the seqdata dir (if it still exists)
  [ ! -e "$run"/seqdata/ ] || \
  rsync -sbav --del --include='pipeline**' --include='SampleSheet*' --include='*.xml' --exclude='*' \
    "$run"seqdata/ "$BACKUP_LOCATION/$run_name/seqdata"

  # And finally the log. Do this last so if copying was interrupted/incomplete it will be obvious.
  # If the log has changed at all during the copy process it's not a problem, because this
  # step will alter the mtime of the directory and trigger a second sync.
  # (I actually discovered this as a bug, but it turns out to be a handy feature!)
  rsync -sa --itemize-changes "$run/pipeline.log" "$BACKUP_LOCATION/$run_name/pipeline.log"
  set +x
  if [ `stat -c %s "$run/pipeline.log"` != $log_size ] ; then
    echo "Log file size has changed during sync. However this should not be a problem as a second"
    echo "sync is going to be triggered."
  fi

  echo "*** Copied FASTQ data and pipeline metadata for $run_name ***"
done
