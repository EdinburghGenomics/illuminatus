#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 2 -t 1-2 -q casava -N Ca053001  -o /ifs/runqc/160530_M01270_0194_000000000-AR1JW/sge_output -e /ifs/runqc/160530_M01270_0194_000000000-AR1JW/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 1 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes1_readlen151_index6nnnn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160530_M01270_0194_000000000-AR1JW' -o '/ifs/runqc/160530_M01270_0194_000000000-AR1JW/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes1_readlen151_index6nnnn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv'   --use-bases-mask Y150n,I6nnnn,Y150n  --tiles=s_[1]   --fastq-compression-level 6  --barcode-mismatches 0 ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "2" ]; then
          echo "Starting Casava for lane: 1 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_10_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_10_lanes1_readlen151_index10";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160530_M01270_0194_000000000-AR1JW' -o '/ifs/runqc/160530_M01270_0194_000000000-AR1JW/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_10_lanes1_readlen151_index10' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_10_forCasava2_17.csv'   --use-bases-mask Y150n,I10,Y150n  --tiles=s_[1]   --fastq-compression-level 6  --barcode-mismatches 0 ;
        fi
        