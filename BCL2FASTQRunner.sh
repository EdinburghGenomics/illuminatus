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

set -e ; set -u

set_bcl2fastq_path() {
    #Pick the appropriate bcl2fastq.
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

CLUSTER_QUEUE="${CLUSTER_QUEUE:-casava}"

if [ "$CLUSTER_QUEUE" = none ] then;
    set_bcl2fastq_path
    #and keep running...
elif [ ! -e /lustre/software ] ; then
    if [ -z "${SGE_TASK_ID:-}" ] ; then
        #I humbly submit myself to the (old) cluster.
        set_bcl2fastq_path
        mkdir -p ./sge_output
        qsub -q "$CLUSTER_QUEUE" "$0"
        exit $?
    fi
else
    if [ -z "${SLURM_JOB_ID:-}" ] ; then
        #I humbly submit myself to the (new) cluster.
        set_bcl2fastq_path
        mkdir -p ./slurm_output
        sbatch -p "$CLUSTER_QUEUE" "$0"
        exit $?
    fi
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
