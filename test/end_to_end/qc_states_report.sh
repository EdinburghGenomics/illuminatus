#!/bin/bash
set -euo pipefail

# Reports the state of all the runs. At some point this will be a real thing.
ENVIRON_SH="${ENVIRON_SH:-./environ.sh}"

# You can report on the live runs from the devel code:
# env RUN_NAME_REGEX='171[012].._.*_.*' ENVIRON_SH=./environ.sh.sample test/end_to_end/qc_states_report.sh

PATH="$(readlink -f "$(dirname $BASH_SOURCE)"/../..):$PATH"
if [ -e "$ENVIRON_SH" ] ; then
    pushd "$(dirname "$ENVIRON_SH")" >/dev/null && \
        source "$(basename "$ENVIRON_SH")"
    popd >/dev/null
fi

debug(){ true ; }
#debug(){ echo "$@" ; } # Uncomment for debugging info

# Same as in driver.sh
RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"
echo "Looking for run directories matching regex $SEQDATA_LOCATION/$RUN_NAME_REGEX/"

# Scan for each run and tot up the number by status
for run in "$SEQDATA_LOCATION"/*/ ; do

  RUNID=`basename "$run"`

  if ! [[ "$RUNID" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring $RUNID - regex mismatch"
    continue
  fi

  # More code nicked from driver.sh
  RUNINFO_OUTPUT="$(RunStatus.py "$run")" || RunStatus.py $run | log 2>&1
  LANES=`grep ^LaneCount: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  STATUS=`grep ^PipelineStatus: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' ' || echo unknown`
  #RUNID=`grep ^RunID: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  INSTRUMENT=`grep ^Instrument: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`
  FLOWCELLID=`grep ^Flowcell: <<< "$RUNINFO_OUTPUT" | cut -f2 -d' '`

  # We assume there is a symlink or else the run ID and the dirname as the same!
  if [ ! -e "$run/pipeline/output" ] && [ ! -e "$FASTQ_LOCATION"/"$RUNID" ] && \
     [ "$STATUS" != new ] && [ "$STATUS" != aborted ] ; then
    echo "$RUNID has a pipeline dir but no fastq directory!"
  fi

  # In BASH, we can emulate a dict with variable names and use built-in array types, like so:
  eval "r_by_status_${STATUS}+=($RUNID)"
  eval "i_by_status_${STATUS}+=($INSTRUMENT)"
  #eval "m_count_${INSTRUMENT}=\$(( \${m_count_${INSTRUMENT}:-0} + 1 ))"

  # If complete, see what version it was done with
  if [ "$STATUS" = "complete" ] ; then
    echo "Run $RUNID completed with pipeline version "`cat $run/pipeline/output/QC/run_info.*.yml | sed -n '/^[ ]*Pipeline Version:/s/.*: //p'`
  fi

done

# Now we need to stash a summary in YAML format:
true "
new:
    rcount: 12
    runs: [id1, id2]
    instruments: [ {name: i1, count: 3}, {name: i2, count: 2} ]
in_qc:
    ...
"
# Printing YAML using shell commands is a bad idea, but I'm doing it anyway, as I don't want to re-write
# all the above in Python just now.

OFH=`mktemp`
exec 10>"$OFH"

#instruments=(`set | grep -o '^m_count_[^=]\+' | cut -c 9-`)

for statusv in `set | grep -o '^r_by_status_[^=]\+'` ; do
    statusn=${statusv:12}
    statusv="${statusv}[@]"
    echo "$statusn:" >&10

    echo "    rcount: `grep -wo '[^ ]*' <<<${!statusv} | wc -l`" >&10

    echo -n "    runs: [" >&10
    echo "${!statusv}]" | sed 's/ /, /g' >&10

    instruv="i_by_status_${statusn}[@]"
    echo -n "    instruments: [" >&10
    grep -wo '[^ ]*' <<<${!instruv} | sort | uniq -c | awk 'BEGIN{ORS=", "}{print "{name: "$2",count: "$1"}"}' | sed 's/, $/]\n/' >&10
done

#If nothing was processed, we need to make an empty dict.
if [ ! -s "$OFH" ] ; then
    echo '{}' >&10
fi

debug "### Run report as YAML:"
debug "`cat "$OFH"`"

# Now lets render that puppy as PDF (needs my msrender script which I'll add to the project)...
# Since the PDF is disposable I'll just clobber it for now.
msrender -d "$OFH" -- "$(dirname $BASH_SOURCE)"/qc_states.gv.tmpl | dot -Tpdf -o "$(dirname $BASH_SOURCE)"/qc_states_scanned.pdf

echo "See PDF in $(dirname $BASH_SOURCE)/qc_states_scanned.pdf"
rm "$OFH"
