#!/bin/bash

# Usage (normally called from driver.sh):
#  cd output_dir #(in which a do_demultiplex.sh script is present)
#  /path/to/BCL2FASTQRunner.sh
#
# The point of this script is to contain the logic necessary to
# run the script (synchronously) on the cluster and to abstract away
# the configuration difference between the old and new clusters, even
# though we don't intend to run the system in production on the old
# cluster.

# SGE settings...
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe qc 8 -t 1-1
#$ -N demultiplexing  -o sge_output -e sge_output

# Do not place any code lines above the SLURM settings...
#SBATCH --wait #This might be unreliable, see slurm_tools/sbatch_wait.sh
#SBATCH -c 8
#SBATCH -J demultiplexing
#SBATCH -o slurm_output/demultiplexing.%A.%a.out
#SBATCH -e slurm_output/demultiplexing.%A.%a.err

set -euo pipefail

set_bcl2fastq_path() {
    # Pick the appropriate bcl2fastq.
    for p in "${BCL2FASTQ_PATH:-}" \
             "/lustre/software/bcl2fastq/bcl2fastq2-v2.17.1.14/bin" \
             "/ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin" \
             ; do
        if [ -d "$p" ] ; then
            echo "Prepending $p to the PATH"
            PATH="$p:$PATH"
            break
        fi
    done
}

echo_and_run(){
    # Run a command, printing what is run and capturing the output
    # (which is assumed to be small!)
    echo "[`pwd`]\$ $*"
    { CMD_OUT="$("$@")" ; CMD_RETVAL=$? ; CMD_FIRSTLINE="$(head -n1 <<<"$CMD_OUT")" ; } || true
    [ -z "$CMD_OUT" ] || cat <<<"$CMD_OUT"
}

check_exit(){
    if [ "$CMD_RETVAL" != 0 ] ; then
        # Diagnosis, please!
        [[ "$CMD_FIRSTLINE" =~ Submitted\ batch\ job\ ([0-9]+) ]] || \
        [[ "$CMD_FIRSTLINE" =~ Your\ job\ ([0-9]+) ]] || true
        JOBID="${BASH_REMATCH[1]:-}"

        if [ -n "$JOBID" ] ; then
            echo "Cluster job exited with an error. Last few lines of the logs are as follows..."
            for log in "`pwd`"/slurm_output/demultiplexing.$JOBID.*.??? \
                       "`pwd`"/sge_output/demultiplexing.?$JOBID.* ; do
                [ ! -e "$log" ] || tail -v -- "$log"
            done
        fi
    else
        echo "$0 finished running cluster job."
    fi
    exit "$CMD_RETVAL"
}


CLUSTER_QUEUE="${CLUSTER_QUEUE:-casava}"

if [ "$CLUSTER_QUEUE" = none ] ; then
    set_bcl2fastq_path
    #and keep running...
elif [ ! -e /lustre/software ] && [ -z "${SGE_TASK_ID:-}" ] ; then
    #I humbly submit myself to the (old) cluster.
    set_bcl2fastq_path
    echo_and_run mkdir -p ./sge_output
    echo_and_run qsub -q "$CLUSTER_QUEUE" "$0"
    check_exit
elif [ -z "${SLURM_JOB_ID:-}" ] ; then
    #I humbly submit myself to the (new) cluster.
    set_bcl2fastq_path
    echo_and_run mkdir -p ./slurm_output
    echo_and_run sbatch -p "$CLUSTER_QUEUE" "$0"
    check_exit
fi

# This part will run on the cluster node.

exec 2>&1 #Everything to stdout
cat <<.
Running in $PWD on $HOSTNAME.
CLUSTER_QUEUE=${CLUSTER_QUEUE:-}
SGE_TASK_ID=${SGE_TASK_ID:-}
SLURM_JOB_ID=${SLURM_JOB_ID:-}

Starting bcl2fastq per ./do_demultiplex.sh...

.
set -x

source ./do_demultiplex.sh
