#!/bin/bash
set -e ; set -u

# Usage (normally called from driver.sh):
#  cd output_dir
#  /path/to/BCL2FASTQRunner.sh

# SGE settings...
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe qc 8 -t 1-1 -q casava
#$ -N demultiplexing  -o sge_output -e sge_output

# SLURM settings...
#SBATCH --wait #This might be unreliable, see slurm_tools/sbatch_wait.sh
#SBATCH -p casava
#SBATCH -c 8
#SBATCH -J demultiplexing
#SBATCH -o slurm_output/demultiplexing.%A.%a.out
#SBATCH -e slurm_output/demultiplexing.%A.%a.err

if [ ! -e /lustre/software ] ; then
    if [ -z "${SGE_TASK_ID:-}" ] ; then
        #I humbly submit myself to the (old) cluster.
        mkdir -p ./sge_output
        qsub "$0"
        exit $?
    fi
else
    if [ -z "${SLURM_JOB_ID:-}" ] ; then
        #I humbly submit myself to the (new) cluster.
        mkdir -p ./slurm_output
        sbatch "$0"
        exit $?
    fi
fi

#Actual cluster job
exec 2>&1 #Everything to stdout
echo $PWD
echo -e "\nSGE_TASK_ID=${SGE_TASK_ID:-}\n"
echo -e "\nSLURM_JOB_ID=${SLURM_JOB_ID:-}\n"

echo "Starting bcl2fastq per do_demultiplex.sh..."
set -x

#Pick the appropriate bcl2fastq.
if [ -e /lustre/software/bcl2fastq/bcl2fastq2-v2.17.1.14/ ] ; then
    PATH="/lustre/software/bcl2fastq/bcl2fastq2-v2.17.1.14/bin/:$PATH"
else
    PATH="/ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/:$PATH"
fi
source ./do_demultiplex.sh
