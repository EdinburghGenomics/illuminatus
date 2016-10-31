#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 8 -t 1-1 -q casava -N Ca0629B12345678  -o /ifs/runqc/160629_E00397_0023_BHM23FCCXX/sge_output -e /ifs/runqc/160629_E00397_0023_BHM23FCCXX/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_lanes12345678_readlen151_index8";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160629_E00397_0023_BHM23FCCXX' -o '/ifs/runqc/160629_E00397_0023_BHM23FCCXX/Unaligned_SampleSheet_in_HiSeq_format_lanes12345678_readlen151_index8' --sample-sheet 'SampleSheet_in_HiSeq_format_forCasava2_17.csv'   --use-bases-mask Y150n,I8,Y150n  --tiles=s_[12345678]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        