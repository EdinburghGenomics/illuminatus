#!/bin/bash
set -eu

# Code from doc/redo.txt. Only suitable for testing just now.
echorun() { echo "$*" ; "$@" ; }

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

echorun cd $myrun
if [ -e failed ] && [ -e qc.started ] ; then
    echo "# Looks like QC failed..."
    echorun rm -f failed qc.started
elif [ -e failed ] && compgen -G "lane?.started" >/dev/null ; then
    echo "# Looks like demultiplexing failed..."
    for f in lane?.started ; do
        echorun touch ${f%.started}.redo
    done
elif [ -e qc.done ] ; then
    echo "# Looks like the run finished, but we can re-make the QC report..."
    echorun rm -f qc.done failed qc.started
else
    echo "# Not sure how to reset this one?!"
fi

