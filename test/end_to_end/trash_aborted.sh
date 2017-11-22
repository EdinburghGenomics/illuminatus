#!/bin/bash
set -euo pipefail

# Trashes output directories for aborted runs, since they will contain trash.
PATH="$(readlink -f "$(dirname $BASH_SOURCE)"/../..):$PATH"
if [ -e "`dirname $BASH_SOURCE`"/../../environ.sh ] ; then
    pushd "`dirname $BASH_SOURCE`/../.." >/dev/null
    source ./environ.sh
    popd >/dev/null
fi

debug(){ true ; }
#debug(){ echo "$@" ; } # Uncomment for debugging info

RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*}"
echo "Looking for run directories matching regex $SEQDATA_LOCATION/$RUN_NAME_REGEX/"

# Scan for each run until we find something that needs dealing with.
for run in "$SEQDATA_LOCATION"/*/ ; do

  RUNID=`basename "$run"`

  # $RUN_NAME_PATTERN is now RUN_NAME_REGEX
  if ! [[ "`basename $run`" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring $RUNID - regex mismatch"
    continue
  fi

  STATUS=`RunStatus.py "$run" | grep ^PipelineStatus: | cut -f2 -d' ' || echo unknown`
  if [ "$STATUS" != aborted ] ; then
    debug "Ignoring $RUNID - status is $STATUS"
    continue
  fi

  # We assume the run ID and the dirname as the same!
  if ! [ -e "$FASTQ_LOCATION"/"$RUNID" ] ; then
    debug "Ignoring $RUNID - no fastq directory"
    continue
  fi

  echo "Trashing $FASTQ_LOCATION/$RUNID..."
  mv -v -t "$FASTQ_LOCATION"/trash -v "$FASTQ_LOCATION"/"$RUNID"
  rm -fv "$run"pipeline/output
done
