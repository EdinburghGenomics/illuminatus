#!/bin/bash

# This script will fetch a new SampleSheet for the current run. It must
# be run in the folder where the sequencer data has been written.
set -e ; set -u

# Firstly, SampleSheet.csv.0 needs to contain the original file from the
# sequencer. It is technically possible to run the machine with no sample
# sheet. In this case, the script will make an empty file.
if [ ! -e SampleSheet.csv.0 ] ; then
    if mv SampleSheet.csv SampleSheet.csv.0 ; then
        echo "SampleSheet.csv renamed as SampleSheet.csv.0"
    else
        echo "SampleSheet.csv.0 created as empty file"
    fi
    ln -s SampleSheet.csv.0 SampleSheet.csv
fi

# At this point we may expect that SampleSheet.csv is a symlink
test -L SampleSheet.csv

# Find a candidate sample sheet, either by looking directly on the smb mount or by
# smbclient or sftp or ...

# For now, just cheat.
cat SampleSheet.csv > SampleSheet.csv.tmp
candidate_ss="SampleSheet.csv.tmp"

if diff -q "$candidate_ss" SampleSheet.csv ; then
    #Nothing to do. Maybe remove CANDIDATE_SS
    echo "SampleSheet.csv is already up-to-date"
else
    #No need to test file existence before writing - just use noclobber
    set noclobber
    counter=1
    while ! cat "$candidate_ss" > "SampleSheet.csv.$counter" ; do
        counter=$(( $counter + 1 ))

        #Just in case there was some other write error
        test $counter -lt 1000
    done

    ln -vsf "SampleSheet.csv.$counter" SampleSheet.csv #Should be safe - we checked it was only a link
fi

rm "$candidate_ss"
