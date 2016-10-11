#!/bin/bash

# Usage (normally called from driver.sh):
#  cd output_dir
#  /path/to/BCL2FASTQRunner.sh

#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe qc 8 -t 1-1 -q casava
#$ -N demultiplexing  -o sge_output -e sge_output

if [ -z "${SGE_TASK_ID:-}" ] ; then
    #I humbly submit myself to the cluster.
    mkdir -p ./sge_output
    qsub "$0"
    exit $?
fi

#Actual cluster job
exec 2>&1 #Everything to stdout
echo $PWD
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

echo "Starting bcl2fastq per do_demultiplex.sh..."
set -x

PATH="/ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/:$PATH"
source ./do_demultiplex.sh
