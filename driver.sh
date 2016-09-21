#!/bin/bash -l
set -e
set -u


# A driver script that is to be called directly from the CRON.
# It will go through all runs in SEQDATA_LOCATION and take action on them.
# As a well behaved CRON job it should only output error messages
# to stdout.
# The script wants to run every 5 minutes or so.

SEQDATA_LOCATION=/home/mberinsk/workspace/illuminatus/test/seqdata_examples
SEQDATA_LOCATION=/ifs/runqc/test_seqdata
FASTQC_LOCATION=/ifs/runqc/test_runqc

RUN_INFO="python3 /home/mberinsk/workspace/illuminatus/bin/RunInfo.py"

DEMULTIPLEXING_PREPROCESSOR="python3 /home/mberinsk/workspace/illuminatus/bin/demultiplexing_preprocessor.py"
DEMULTIPLEXING_RUNNER="bash /home/mberinsk/workspace/illuminatus/bin/demultiplexing_runner.sh"
DEMULTIPLEXING_POSTPROCESSOR="python3 /home/mberinsk/workspace/illuminatus/bin/demultiplexing_postprocessor.py"
DEMULTIPLEXING_CLEANUP="python3 /home/mberinsk/workspace/illuminatus/bin/demultiplexing_cleanup.py"

MAINLOG=/tmp/logs/autorun.`date +%Y%m%d`.log

trap 'echo "=== `date`. Finished run; PID=$$ ===" >> "$MAINLOG"' EXIT

# 1) Refuse to run on a machine other than headnode1
if [[ "${HOSTNAME%%.*}" != headnode1 ]] ; then
    echo "This script should only be run on headnode1"
    exit 1
fi

# 2) If $0 is not a canonical path, gripe
if [[ $(readlink -f "$0") != "$0" ]] ; then
    echo "You need to run this script by absolute path: $(readlink -f "$0")"
    exit 1
fi

# 3) Ensure I the directory is there for the main log file.
mkdir -p `dirname "$MAINLOG"`

# 4) We're good to go!
echo >> "$MAINLOG"
echo "=== `date`. Running $0; PID=$$ ===" >> "$MAINLOG"

# To avoid logs piling up in all project folders, use logrotate to cycle out
# the old ones. Assuming we let this run every 5 mins, 2016 logs is 7 days.
rotlog() {
    /usr/sbin/logrotate -f -s `mktemp` /dev/stdin <<.
"`pwd`/$1" {
    rotate 2016
    missingok
}
.
}

# 5) Run the run info module for each run until we find something we can run the pipeline on.
for run in $SEQDATA_LOCATION/*; 
do
  # invoke runinfo and collect some meta-information about the run 
  RUNINFO_OUTPUT="`$RUN_INFO $run`"

  LANES=`grep ^LaneCount: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  STATUS=`grep ^Status: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  RUNID=`grep ^RunID: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  INSTRUMENT=`grep ^Instrument: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`

  echo "Folder $run contains $RUNID from machine $INSTRUMENT with $LANES lane(s) and status $STATUS" >> "$MAINLOG"
 
  # define an action for each possible status that a run can have:
  # 1) new - this run is seen for the first time (sequencing might be done or is still in progress)
  # 2) reads_finished - sequencing has finished, the pipeline/ folder exists the pipeline was not started yet...
  # 3) in_pipeline - the pipeline started processing at least one lane of this run but has not yet finished
  # 4) complete - the pipeline has finished processing ALL lanes of this run
  # 5) redo - at least one lane is marked for redo and 4)
  # 6) unknown - anything else, including run folders without RunInfo.xml

  if [[ $STATUS == new ]] ; then
    # nothing for now but could send a notification email or create a pipeline/ folder...
    echo "\_Creating pipeline/ folder for run $RUNID" >> $MAINLOG
    (
      mkdir $run/pipeline/
    ) && echo "OK" >> "$MAINLOG" && exit 0 || echo $FAIL >> "$MAINLOG"
  fi

  if [[ $STATUS == reads_finished ]] ; then
    # need to kick off the demultiplexing here
    DEMUX_OUTPUT_FOLDER="$FASTQC_LOCATION/$RUNID/demultiplexing/"
    echo "\_READS_FINISHED starting demultiplexing for $run into $DEMUX_OUTPUT_FOLDER" >> $MAINLOG
    (
    mkdir -p $DEMUX_OUTPUT_FOLDER
    $DEMULTIPLEXING_PREPROCESSOR $run $DEMUX_OUTPUT_FOLDER
    $DEMULTIPLEXING_RUNNER $DEMUX_OUTPUT_FOLDER
    #$DEMULTIPLEXING_POSTPROCESSOR $DEMUX_OUTPUT_FOLDER
    ) && echo OK >> "$MAINLOG" && exit 0 || echo $FAIL >> "$MAINLOG"
  fi

  if [[ $STATUS == in_pipeline ]] ; then
    # in pipeline, could update some progress status
    echo "\_IN_PIPELINE $run" >> "$MAINLOG"
  fi

  if [[ $STATUS == complete ]] ; then
    # the pipeline completed for this run ... nothing to be done ...
    echo "\_COMPLETE $run" >> "$MAINLOG"
  fi

  if [[ $STATUS == redo ]] ; then
    # the pipeline completed for this run ... nothing to be done ...
    echo "\_REDO $run" >> "$MAINLOG"
    (exit 1
    $DEMULTIPLEXING_CLEANUP
    $DEMULTIPLEXING_PREPROCESSOR
    $DEMULTIPLEXING_RUNNER
    $DEMULTIPLEXING_POSTPROCESSOR
    ) && echo OK >> "$MAINLOG" && exit 0 || echo FAIL >> "$MAINLOG"
  fi

  if [[ $STATUS == unknown ]] ; then
    # this run either has no RunInfo.xml or an invalid set of touch files ... nothing to be done...
    echo "\_skipping because status is $STATUS" >> "$MAINLOG"
  fi

done

