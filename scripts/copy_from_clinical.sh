#!/bin/bash
set -ue

## Script to help you copy a run over from Clinical when they ran it on a HiSeq X.
## This can be done in one shot, but the advantage of the method used by this script
## is that you will get a preliminary Illuminatus report and a run ticket right away.

# We'll need this in a bit.
yesno(){
    while true ; do
        read -p "${1:-?} [y/n] " -n1 answer
        if [ "$answer" = 'y' -o "$answer" = 'Y' ] ; then
            echo es >&2 ; return 0
        elif [ "$answer" = 'n' -o "$answer" = 'N' ] ; then
            echo o >&2 ; return 1
        fi
        echo '?' >&2
    done
}

echo "--> Clinical->GS run copy helper <--"
echo

sdir=import_staging
spath="${1:-}"
spath="${spath%/}"
bpath="${spath%%:*}"
runid="${spath##*/}"

if [ -z "$runid" ] ; then
    echo "You must specify a source to be copied - eg."
    echo " tbooth@transfer.epcc.ed.ac.uk:KB_flowcells/181005_E00306_0379_AHMW7XXXXY"
    echo ""
    echo "See the book of truth for the correct shared account name (if not tbooth) and the password."
    exit 1
fi

# See if $runid is already here
if [ -e "$runid" ] || [ -e ../"$runid" ] ; then
    echo "Run $runid is already here. Refusing to overwrite it."
    exit 1
fi

if [ "$(basename "$(pwd -P)")" != "$sdir" ] ; then
    echo "This script normally expects to run in $sdir."
    echo "Are you really sure you want to run it in `pwd -P`?"

    if ! yesno ; then
        echo "OK so I'll stop here."
        exit 0
    fi
fi

# Now we want to get the password and hold on to it, otherwise the user gets prompted
# to type the password again half way through the transfer.
while true ; do
    read -p "Password for $bpath: " -s apass ; echo

    # See if aspera likes it.
    export ASPERA_SCP_PASS="$apass"
    foo=`ascp $bpath:__PING__ /tmp 2>&1 || true`

    if [[ "$foo" =~ No.such.file.or.directory ]] ; then
        # This is good!
        break
    elif [[ "$foo" =~ failed.to.authenticate ]] ; then
        # Try again
        echo "$foo. Please try again."
        continue
    else
        echo "Unexpected response trying to ping server $bpath:"
        echo "$foo"
        exit 1
    fi
done

# Copy the run - round 1
# For some reason I can't get -N to work, so exclude instead.
echo "Copying the skeleton run..."
ascp -E 'Data' -E '*Logs' -E 'PeriodicSaveRates' -E '*Images' -E 'Recipe' -E 'RTA*' -E '*.txt' "$spath" .

echo "Moving initial directory to parent."
mv -v "$runid" ..

# Copy the run - round 2. It's important I don't copy any directories twice or the move will fail.
echo "Copying the full run..."
ascp -E '*/Thumbnail_Images/**' -E '*/PeriodicSaveRates/**' -E '*.csv' -E 'Config' -E 'InterOp' "$spath" .

echo "Full run copied. Moving all files to parent."
mv -v -t ../"$runid"/ "$runid"/*
rmdir -v "$runid"

echo "DONE - the pipeline should now start read1 processing and demultiplexing"
