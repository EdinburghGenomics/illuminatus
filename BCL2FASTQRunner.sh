#!/usr/bin/bash

 
#    Actually runs bcl2fastq on the cluster
#    Usage BCL2FASTQRunner.py <dest_dir>

cd $1

mkdir sge_output/

# the script was prepared by the preprocessor
qsub sge_demultiplex.sh
