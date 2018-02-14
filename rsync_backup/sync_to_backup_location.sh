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

# Now loop through all the project in a similar way to the driver and the state reporter.
# But note we loop through $FASTQDATA_LOCATION
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

  # If the pipeline dir is missing, sync it on suspicion.
  # Maybe I should RSYNC anyway here and not wait for final QC?
  if [ -e "$run/seqdata/pipeline" ] && [ ! -e "$run/seqdata/pipeline/qc.done" ] ; then
    debug "Ignoring incomplete $run_name"
    continue
  fi

  # If the pipeline.log is missing we have problems
  if [ ! -e "$run/pipeline.log" ] ; then
    echo "Missing $run/pipeline.log - something is wrong here! Run will not be copied!"
    continue
  fi

  # Comparing times on pipeline.log is probably the simplest way to see if the copy
  # is up-to-date and saves my sync-ing everything again and again
  if rsync -nsa --itemize-changes --include='pipeline.log' --exclude='*' "$run" "$BACKUP_LOCATION/$run_name" | grep -qF pipeline.log ; then
    log_size=`stat -c %s "$run/pipeline.log"`
    debug "Detected new pipeline log activity for $run_name with log size $log_size"
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

  rsync -sav --exclude='**/.snakemake' --exclude='**/slurm_output' --exclude=seqdata --exclude=pipeline.log \
    "$run" "$BACKUP_LOCATION/$run_name"

  # Just to test the log catcher below we can...
  # echo BUMP >> "$run/pipeline.log"

  # Now add the pipeline directory and the SampleSheets
  rsync -sav --include='pipeline**' --include='SampleSheet*' --include='*.xml' --exclude='*' \
    "$run"seqdata/ "$BACKUP_LOCATION/$run_name/seqdata"

  # And finally the log. Do this last so if copying was interrupted/incomplete it will be obvious.
  # If the log has changed size during the copy process it's a problem.
  # My solution is to touch the pipeline.log so the next iteration will spot it and re-sync.
  rsync -sa --itemize-changes "$run/pipeline.log" "$BACKUP_LOCATION/$run_name/pipeline.log"
  if [ `stat -c %s "$run/pipeline.log"` != $log_size ] ; then
    echo "Log file size has changed during sync. To ensure that no new data is missed, the timestamp"
    echo "on this file will be updated now, which will trigger a re-sync on the next scan."
    sleep 1 ; touch "$run/pipeline.log"
  fi

  echo "*** Copied FASTQ data and pipeline metadata for $run_name ***"
done
