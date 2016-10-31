#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 8 -t 1-1 -q casava -N Ca0811B12345678  -o /ifs/runqc/160811_D00261_0355_BC9DA7ANXX/sge_output -e /ifs/runqc/160811_D00261_0355_BC9DA7ANXX/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_lanes12345678_readlen51_index6";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160811_D00261_0355_BC9DA7ANXX' -o '/ifs/runqc/160811_D00261_0355_BC9DA7ANXX/Unaligned_SampleSheet_in_HiSeq_format_lanes12345678_readlen51_index6' --sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'   --use-bases-mask Y50n,I6  --tiles=s_[12345678]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        