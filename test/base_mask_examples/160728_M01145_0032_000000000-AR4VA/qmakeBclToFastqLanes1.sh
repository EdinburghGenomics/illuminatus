#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 2 -t 1-1 -q casava -N Ca072801  -o /ifs/runqc/160728_M01145_0032_000000000-AR4VA/sge_output -e /ifs/runqc/160728_M01145_0032_000000000-AR4VA/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 1 samplesheet: SampleSheet_in_HiSeq_format_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_lanes1_readlen150_index6";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160728_M01145_0032_000000000-AR4VA' -o '/ifs/runqc/160728_M01145_0032_000000000-AR4VA/Unaligned_SampleSheet_in_HiSeq_format_lanes1_readlen150_index6' --sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'   --use-bases-mask Y149n,I6,Y149n  --tiles=s_[1]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        