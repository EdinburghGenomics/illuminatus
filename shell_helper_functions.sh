#!/bin/bash

## Helper functions for shell scripts.
__EXEC_DIR="${EXEC_DIR:-`basename $BASH_SOURCE`}"

# All the Snakefiles have bootstrapping scripts on them, but this script
# will run snakemake directly via the shell helper functions.
export LOCAL_JOBS=${LOCAL_JOBS:-2}
export SNAKE_THREADS=${SNAKE_THREADS:-200}
export DRY_RUN=${DRY_RUN:-0}

## Dump out the right cluster config (just now we only have one)
function cat_cluster_yml(){
    cat "`dirname $0`"/cluster.slurm.yml
}

find_toolbox() {
    # The toolbox used by the pipeline can be set by setting TOOLBOX in the
    # environment (or environ.sh). Otherwise look for it in the program dir.
    _toolbox="$( cd $(dirname "$BASH_SOURCE") && readlink -f ${TOOLBOX:-toolbox} )"
    echo "$_toolbox"

    if ! [ -e "$_toolbox/" ] ; then
        echo "WARNING - find_toolbox - No such directory ${_toolbox}" >&2
    fi
}

# Functions to run a Snakefile
find_snakefile() {
    #Is it in the CWD (or an absolute path)?
    if [ -e "$1" ] ; then
        echo "$1"
    #Maybe it's in the folder with this script
    elif [ -e "$__EXEC_DIR/$1" ] ; then
        echo "$__EXEC_DIR/$1"
    #I give up.  Echo back the name so I get a sensible error
    else
        echo "$1"
    fi
}

snakerun_drmaa() {
    CLUSTER_QUEUE="${CLUSTER_QUEUE:-edgen-casava}"

    if [ "$CLUSTER_QUEUE" = none ] ; then
        snakerun_single "$@"
        return
    fi

    snakefile=`find_snakefile "$1"` ; shift
    # Ensure the active VEnv gets enabled on cluster nodes:
    if [ -n "${VIRTUAL_ENV:-}" ] ; then
        export SNAKE_PRERUN="${VIRTUAL_ENV}/bin/activate"
    fi

    # Spew out cluster.yaml
    [ -e cluster.yml ] || cat_cluster_yml > cluster.yml

    # Ensure Snakemake uses the right wrapper script.
    # In particular this sets TMPDIR
    _jobscript="`find_toolbox`/snakemake_jobscript.sh"

    # With alternative --drmaa args and cluster.yml this could run on
    # SGE. See v1.4.6 for the old code that actually supported this.
    echo
    echo "Running $snakefile in `pwd` on the SLURM cluster"
    SNAKE_THREADS="${SNAKE_THREADS:-100}"
    EXTRA_SNAKE_FLAGS="${EXTRA_SLURM_FLAGS:-}"
    EXTRA_SLURM_FLAGS="${EXTRA_SLURM_FLAGS:--t 24:00}"

    mkdir -p ./slurm_output
    set -x
    snakemake \
         -s "$snakefile" -j $SNAKE_THREADS -p --rerun-incomplete \
         ${EXTRA_SNAKE_FLAGS} --keep-going --cluster-config cluster.yml \
         --jobname "{rulename}.snakejob.{jobid}.sh" \
         --drmaa " ${EXTRA_SLURM_FLAGS} -p ${CLUSTER_QUEUE} {cluster.slurm_opts} \
                   -e slurm_output/{rule}.snakejob.%A.err \
                   -o slurm_output/{rule}.snakejob.%A.out \
                 " \
         "$@"

}

snakerun_single() {
    snakefile=`find_snakefile "$1"` ; shift

    echo
    echo "Running $snakefile in `pwd` in local mode"
    snakemake \
         -s "$snakefile" -j $LOCAL_JOBS -p --rerun-incomplete \
         "$@"
}

snakerun_touch() {
    snakefile=`find_snakefile "$1"` ; shift

    echo
    echo "Running $snakefile --touch in `pwd` to update file timestamps"
    snakemake -s "$snakefile" --quiet --touch "$@"
    echo "DONE"
}


if [ "$0" = "$BASH_SOURCE" ] ; then
    echo "Source this file in your BASH script to make use of the helper functions."

    echo
    echo "Here is the cluster config..."
    cat_cluster_yml
fi

