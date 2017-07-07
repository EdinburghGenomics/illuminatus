#!/bin/bash

## Helper functions for shell scripts.
__EXEC_DIR="${EXEC_DIR:-`basename $BASH_SOURCE`}"

## boolean - are we on the new cluster or not?
function is_new_cluster(){
   [ -d /lustre/software ]
}

## Dump out the right cluster config
function cat_cluster_yml(){
    cat "`dirname $0`"/cluster.`is_new_cluster && echo slurm || echo sge`.yml
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
    snakefile=`find_snakefile "$1"` ; shift
    export SNAKE_PRERUN="$QC_TOOLS_ACTIVATE"

    # Spew out cluster.yaml
    [ -e cluster.yml ] || cat_cluster_yml > cluster.yml

    if is_new_cluster ; then
        echo "Running $snakefile on the GSEG cluster"
        __SNAKE_THREADS="${SNAKE_THREADS:-100}"

        mkdir -p ./slurm_output
        snakemake \
             -s "$snakefile" -j $__SNAKE_THREADS -p -T --rerun-incomplete \
             ${EXTRA_SNAKE_FLAGS:-} --keep-going --cluster-config cluster.yml \
             --jobname "{project_id}{rulename}.snakejob.{jobid}.sh" \
             --drmaa " -p qc {cluster.slurm_opts} \
                       -e slurm_output/{rule}.snakejob.{jobid}.%A.err \
                       -o slurm_output/{rule}.snakejob.{jobid}.%A.out \
                     " \
             "$@"

    else
        echo "Running $snakefile on the old cluster"
        __SNAKE_THREADS="${SNAKE_THREADS:-20}"

        mkdir -p ./sge_output
        snakemake \
             -s "$snakefile" -j $__SNAKE_THREADS -p -T --rerun-incomplete \
             ${EXTRA_SNAKE_FLAGS:-} --keep-going --cluster-config cluster.yml \
             --jobname "S{project_id}{rulename}.{jobid}.sh" \
             --drmaa " -q qc -cwd -v SNAKE_PRERUN='$SNAKE_PRERUN' -p -10 -V \
                       -pe {cluster.pe} -l h_vmem={cluster.mem} {cluster.extra} \
                       -o sge_output -e sge_output \
                     " \
             "$@"
    fi
}

snakerun_single() {
    snakefile=`find_snakefile "$1"` ; shift

    if is_new_cluster ; then __LOCALJOBS=4 ; else __LOCALJOBS=1 ; fi

    echo "Running $snakefile in local mode"
    snakemake \
         -s "$snakefile" -j $__LOCALJOBS -p -T --rerun-incomplete \
         "$@"
}

snakerun_touch() {
    snakefile=`find_snakefile "$1"` ; shift

    echo "Running $snakefile --touch to update file timestamps"
    snakemake -s "$snakefile" --quiet --touch "$@"
    echo "DONE"
}


# All the Snakefiles have bootstrapping scripts on them, but this script
# will run snakemake directly via the shell helper functions.
if is_new_cluster ; then
    export SNAKE_THREADS=${SNAKE_THREADS:-200}
else
    export SNAKE_THREADS=${SNAKE_THREADS:-25}
fi
export DRY_RUN=${DRY_RUN:-0}


if [ "$0" = "$BASH_SOURCE" ] ; then
    echo "Source this file in your BASH script to make use of the helper functions."

    echo
    echo "Here is the cluster config..."
    cat_cluster_yml
fi

