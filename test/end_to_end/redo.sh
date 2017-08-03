#!/bin/bash
set -eu

# Code from doc/redo.txt. Only suitable for testing just now.
echorun() { echo "$*" ; "$@" ; }

# Huess the last run I was tinkering with.
myrun="`ls -dt $SEQDATA_LOCATION/*/pipeline | head -n 1`"

echorun cd $myrun
if compgen -G "lane?.failed" >/dev/null ; then
    echo "# Looks like demultiplexing failed..."
    for f in lane?.failed ; do
        echorun touch ${f%.failed}.redo
    done
elif [ -e failed ] && [ -e qc.started ] ; then
    echo "# Looks like QC failed..."
    echorun rm -f failed qc.started
else
    echo "# Not sure how to reset this one?!"
fi

