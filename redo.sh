#!/bin/bash
set -eu

# This script helps you to redo a failed run or a lane that needs
# redeumultiplexing after fixing the sample sheet.

# Eventually I'd like to re-code it and make it available as a web service
# so that people can trigger re-runs direct from the LIMS (or the dashboard
# or wherever).

if [ "${DRY_RUN:-0}" != 0 ] ; then
    echorun() { echo DRY_RUN: "$*" ; }
else
    echorun() { echo "$*" ; "$@" ; }
fi

yesno(){
    while true ; do
        read -p '[y/n] ' -n1 answer
        if [ "$answer" = 'y' -o "$answer" = 'Y' ] ; then
            echo yes ; echo >&2 ; break
        elif [ "$answer" = 'n' -o "$answer" = 'N' ] ; then
            echo no ; echo >&2 ; break
        fi
        echo '?' >&2
    done
}

chooser(){
    while true ; do
        read -p "[$*] " -n1 answer
        if [[ "$*" =~ "$answer" ]] ; then
            echo "$answer" ; echo >&2 ; break
        fi
        echo '?' >&2
    done
}

# First load up the configuration.
if [ -e "`dirname $BASH_SOURCE`"/environ.sh ] ; then
    pushd "`dirname $BASH_SOURCE`" >/dev/null
    set -x
    source ./environ.sh
    set +x
    popd >/dev/null
fi

redo_all_lanes(){
    # Assume we are in the pipeline dir
    for f in lane?.started lane?.done ; do
        [ -e ${f%.*}.redo ] || echorun touch ${f%.*}.redo
    done
}

redo_some_lanes(){
    for f in lane?.started lane?.done ; do
        if [ ! -e ${f%.*}.redo ] ; then
            echo -n "Re-do ${f%.*}? "
            if [ `yesno` = yes ] ; then
                echorun touch ${f%.*}.redo
            fi
        fi
    done
}

# Now work out what run we are trying to operate on.
if [ -n "${1:-}" ] ; then
    myrun="${SEQDATA_LOCATION}/$1/pipeline"
elif [ -e "$SEQDATA_LOCATION/${RUN_NAME_REGEX:-0/0/0}" ] ; then
    # Run name regex is set and specifies a single run.
    # Maybe I should grep this properly?
    myrun="${SEQDATA_LOCATION}/${RUN_NAME_REGEX}/pipeline"
else
    # Guess the last run that failed and was not aborted.
    myrun=''
    for somerun in `ls -at "$SEQDATA_LOCATION"/*/pipeline/failed` ; do
        somerun="$(dirname "$somerun")"
        if [[ "$(basename $(dirname "$somerun"))" =~ ^${RUN_NAME_REGEX}$ ]] && \
           [ ! -e "$somerun"/pipeline/aborted ] ; then
           echo "Last failed run I can see was $somerun"
           myrun=somerun
           break
        fi
    done
    myrun="`ls -dt $SEQDATA_LOCATION/*/pipeline | head -n 1`"
fi

cd $myrun
echo "CWD is now `pwd`"

# Now see what is wrong...
# RunStatus.py mirrors this logic but does not differentiate between demultiplexing
# failed and QC failed.
if [ -e aborted ] ; then
    echo "# The run was aborted. De-abort it and redo?"
    if [ `yesno` = yes ] ; then
        echorun rm aborted
        redo_all_lanes
    fi

elif [ -e failed ] && [ -e qc.started ] ; then
    echo "# Looks like QC failed. What to do?"
    echo "   1. Resume QC"
    echo "   2. Restart QC from scratch"
    echo "   3. Re-do demultiplexing of all lanes"
    echo "   4. Re-do demultiplexing of selected lanes (then resume QC)"
    answer=`chooser 1 2 3 4`

    if [ $answer = 1 ] ; then
        echorun rm -f failed qc.started
    elif [ $answer = 2 ] ; then
        echorun rm -f failed qc.started
        echorun mv output/QC output/QC.old
    elif[ $answer = 3 ] ; then
        redo_all_lanes
    elif[ $answer = 4 ] ; then
        redo_some_lanes
    fi

elif [ -e failed ] && compgen -G "lane?.started" >/dev/null ; then
    echo "# Looks like demultiplexing failed. What to do?"
    echo "   1. Re-do demultiplexing of all lanes (recommended)"
    echo "   2. Re-do demultiplexing of selected lanes"
    if [ $answer = 1 ] ; then
        redo_all_lanes
    elif [ $answer = 2 ] ; then
        redo_some_lanes
    fi

elif [ -e qc.done ] ; then
    echo "# Looks like the run finished. What to do?"
    echo "   1. Re-generate QC report"
    echo "   2. Restart QC from scratch"
    echo "   3. Re-do demultiplexing of all lanes"
    echo "   4. Re-do demultiplexing of selected lanes"
    answer=`chooser 1 2 3 4`

    if [ $answer = 1 ] ; then
        echorun rm -f qc.started qc.done
    elif [ $answer = 2 ] ; then
        echorun rm -f qc.started qc.done
        echorun mv output/QC output/QC.old
    elif[ $answer = 3 ] ; then
        redo_all_lanes
    elif[ $answer = 4 ] ; then
        redo_some_lanes
    fi

elif compgen -G "lane?.started" >/dev/null || compgen -G "qc.started" >/dev/null ; then
    echo "# Looks like the pipeline is still running!"
    echo "Are you sure that it is not possible the pipeline may or may not be still running?"
    yesno
    echo "Really?"
    yesno
    echo "But seriously, if you are sure the pipeline crashed you can restart it from the top."
    echo "This action will forcibly remove the .snakemake lock directories, so if the pipeline really was"
    echo "running it will get in a massive mess."
    echo "   1. Re-do demultiplexing of all lanes and remove locks"
    echo "   2. Don't do that"
    echo "   3. No action"
    echo "   4. Abort"
    echo "   5. This is not even an option"
    answer=`chooser 1 2 3 4`

    if [ $answer = 1 ] ; then
        redo_all_lanes
        echorun rm -rf output/.snakemake output/demultiplexing/.snakemake
    fi

else
    echo "# Not sure how to reset this one?! Here's whay I see in the pipeline dir:"
    ls -l
fi

