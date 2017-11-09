#!/bin/bash
set -eu

# Examine why a QC failed. Basically, find the last job that failed and
# print the slurm error log.
echorun() { echo "$*" ; "$@" ; }

if [ -e "`dirname $BASH_SOURCE`"/../../environ.sh ] ; then
    pushd "`dirname $BASH_SOURCE`/../.." >/dev/null
    source ./environ.sh
    popd >/dev/null
fi

# Same as for redo, work out which run we thing we're looking at
if [ -n "${1:-}" ] ; then
    myrun="${SEQDATA_LOCATION}/$1/pipeline"
elif [ -e "$SEQDATA_LOCATION/${RUN_NAME_REGEX:-}" ] ; then
    # Run name regex is set and specifies a single run.
    # Maybe I should grep this properly?
    myrun="${SEQDATA_LOCATION}/${RUN_NAME_REGEX}/pipeline"
else
    # Guess the last run I was tinkering with.
    myrun="`ls -dt $SEQDATA_LOCATION/*/pipeline | head -n 1`"
fi

echo "==> Last few errors in $myrun/pipeline_read1.log <==" | env GREP_COLORS='mt=01;35' grep --color=always '.*'

grep --color=always '^Error executing rule' "$myrun"/pipeline_read1.log | tail -n 5
echo

lastfail=`grep '^Error executing rule' "$myrun"/pipeline_read1.log | grep -o 'external: [0-9]\+' | awk '{print $2}' | tail -n 1`

slurm_dir="$FASTQ_LOCATION/$(basename $(dirname "$myrun"))"/slurm_output
tail -v -n 50 "$slurm_dir/"*.$lastfail.??? | env GREP_COLORS='mt=01;35' grep --color=always '==>.*\|^'
