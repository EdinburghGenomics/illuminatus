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
# Where are runs going to?
echo "Backing up data from $FASTQ_LOCATION to $BACKUP_LOCATION"

# We can supply a BACKUP_NAME_REGEX or fall back to RUN_NAME_REGEX (the default here
# should match the one hard-coded in driver.sh)
RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"
RUN_NAME_REGEX="${BACKUP_NAME_REGEX:-$RUN_NAME_REGEX}"
debug "RUN_NAME_REGEX=$RUN_NAME_REGEX"

# Now loop through all the project in a similar way to the driver and the state reporter.
# But note we loop through $FASTQDATA_LOCATION
for run in "$FASTQDATA_LOCATION"/*/ ; do

  run_name="`basename $run`"

  # Apply filter
  if ! [[ "$run_name" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring $run_name which does not match regex"
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
  if [ -e "$run/seqdata/pipeline" ] && [ ! -e "$run/seqdata/pipeline/qc.finished" ] ; then
    debug "Ignoring incomplete $run_name"
  fi

  # Maybe we should have a time cutoff? Look for anything in pipeline less than N days old.
  # There should be no changes in the output without some record in the pipeline.
  # if [ -e "$run/seqdata/pipeline" ] && [ "${BACKUP_MAX_DAYS:-0}" != 0 ]  ; then
  #   if find "$run/seqdata/pipeline" -mtime -"$BACKUP_MAX_DAYS" | grep -q . ; then
  #     debug "Found recent pipeline activity for $run_name"
  #   else
  #     debug "No recent pipeline activity for $run_name"
  #     continue
  #   fi
  # else

  # I could alternatively look at pipeline.log - simpler.
  if [ -e "$run/pipeline.log" ] && [ "${BACKUP_MAX_DAYS:-0}" != 0 ]  ; then
    if find "$run/pipeline.log" -mtime -"$BACKUP_MAX_DAYS" | grep -q . ; then
      debug "Found recent pipeline activity logged for $run_name"
    else
      debug "No recent pipeline activity for $run_name"
      continue
    fi
  else
    echo "Backing up $run_name regardless of last activity"
  fi

  # === OK, here we go with the actual sync... ===
  echo "*** Starting sync for $run_name ***"

  if [ "${BACKUP_DRY_RUN:-0}" != 0 ] ; then
    echo "*** DRY_RUN - skipping ***"
    continue
  fi

  rsync -av --exclude=.snakemake --exclude=slurm_output --exclude=seqdata \
    "$run" $BACKUP_LOCATION

  # Now add the pipeline directory and the SampleSheets
  rsync -av --include=pipeline --include='SampleSheet*' --include='*.xml'
    "$run"/seqdata $BACKUP_LOCATION

  echo "*** Copied FASTQ data and pipeline metadata for $run_name ***"
done
