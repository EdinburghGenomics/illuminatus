#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 8 -t 1-2 -q casava -N Ca0825A12345678  -o /ifs/runqc/160825_D00261_0357_AC9M41ANXX/sge_output -e /ifs/runqc/160825_D00261_0357_AC9M41ANXX/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes23578_readlen51_index6nnnnnnnnnn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160825_D00261_0357_AC9M41ANXX' -o '/ifs/runqc/160825_D00261_0357_AC9M41ANXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes23578_readlen51_index6nnnnnnnnnn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv'   --use-bases-mask Y50n,I6nn,nnnnnnnn  --tiles=s_[23578]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "2" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_lanes146_readlen51_index16";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160825_D00261_0357_AC9M41ANXX' -o '/ifs/runqc/160825_D00261_0357_AC9M41ANXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_lanes146_readlen51_index16' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_forCasava2_17.csv'   --use-bases-mask Y50n,I8,I8  --tiles=s_[146]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        