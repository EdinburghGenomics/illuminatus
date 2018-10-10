#!/bin/bash

## Script to help you copy a run over from Clinical when they ran it on a HiSeq X.
## This can be done in one shot, but the advantage of this method is that you will
## get a preliminary Illuminatus report and a run ticket right away.

# We'll need this in a bit.
yesno(){
    while true ; do
        read -p "$1 [y/n] " -n1 answer
        if [ "$answer" = 'y' -o "$answer" = 'Y' ] ; then
            echo es >&2 ; return 0
        elif [ "$answer" = 'n' -o "$answer" = 'N' ] ; then
            echo o >&2 ; return 1
        fi
        echo '?' >&2
    done
}

echo "Clinical->GS run copy helper"

sdir=/lustre/seqdata/import_staging
spath="${1%/}"
runid="${spath##*/}"

if [ -z "$runid" ] ; then
    echo "Please give a source to be copied - eg."
    echo " tbooth@transfer.epcc.ed.ac.uk:KB_flowcells/181005_E00306_0379_AHMW7XXXXY"
    echo ""
    echo "See the book of truth for the correct shared account name (if not tbooth) and the password."
    exit 1
fi

# See if $runid is already here
if [ -e "$runid" ] || [ -e ../"$runid" ] ; then
    echo "Run $runid is already here. Refusing to overwrite it."
fi

if [ "`pwd -P`" != "$sdir" ] ; then
    echo "This script normally expects to run in $sdir."
    echo "Are you really sure you want to run it in `pwd -P`?"

    if ! yesno ; then
        echo "OK so I'll stop here."
        exit 0
    fi
fi

# Copy the run - round 1
ascp -E '*/Thumbnail_Images/**' "$spath" .

echo "Moving initial directory to parent."
mv -v "$runid" ..

# Copy the run - round 2
ascp -E '*/Thumbnail_Images/**' "$spath" .

echo "Full run copied. Moving all files to parent."
mv -v -t ../"$runid" "$runid"/*
rmdir -v "$runid"

echo "DONE - the pipeline shoud now start"
