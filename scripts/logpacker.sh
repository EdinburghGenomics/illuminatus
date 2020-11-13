#!/bin/bash
set -eu

# Very basic log packer. Run it in the current directory, then run the commands
# it prints.

# 1) Find the candidate months to pack.

candidates=($(find -regextype posix-egrep -maxdepth 1 -type f -regex '\./\w+.[0-9]{8}.log' | egrep -o '\w+.[0-9]{6}' | sort -u))

# 2) Go through the list

for c in "${candidates[@]}" ; do

    # Calculate the time difference. The number here is meaningless but we only need
    # to test that it is > 0
    pseudo_age=$(( `date +'%Y%m'` - ${c#*.} ))

    if [ -e "archive/${c}_all.tar.xz" ] ; then
        echo "## ERROR: File archive/${c}_all.tar.xz already exists"
    elif ! [ $pseudo_age -gt 0 ] ; then
        echo "## Skipping ${c}_all.tar.xz as it is not old enough"
    else
        echo "tar -cvaf archive/${c}_all.tar.xz ${c}??.log && rm -v ${c}??.log"
    fi
done
