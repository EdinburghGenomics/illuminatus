#!/bin/bash
set -e
set -u

# Add the seqdata/output links if they were not there already.
# Works in either dir but only for default locations.

if [ "`dirname $PWD`" = '/lustre/seqdata' ] ; then
    cd /lustre/fastqdata/"`basename $PWD`"
fi

if [ "`dirname $PWD`" = '/lustre/fastqdata' ] ; then
    ln -vs /lustre/seqdata/"`basename $PWD`" seqdata
    ln -vs /lustre/fastqdata/"`basename $PWD`" seqdata/pipeline/output
fi
