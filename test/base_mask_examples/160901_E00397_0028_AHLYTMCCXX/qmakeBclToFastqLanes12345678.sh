#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 8 -t 1-2 -q casava -N Ca0901A12345678  -o /ifs/runqc/160901_E00397_0028_AHLYTMCCXX/sge_output -e /ifs/runqc/160901_E00397_0028_AHLYTMCCXX/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes3_readlen151_index6nn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160901_E00397_0028_AHLYTMCCXX' -o '/ifs/runqc/160901_E00397_0028_AHLYTMCCXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes3_readlen151_index6nn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv'   --use-bases-mask Y150n,I6nn,Y150n  --tiles=s_[3]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "2" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_lanes1245678_readlen151_index8";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160901_E00397_0028_AHLYTMCCXX' -o '/ifs/runqc/160901_E00397_0028_AHLYTMCCXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_lanes1245678_readlen151_index8' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_forCasava2_17.csv'   --use-bases-mask Y150n,I8,Y150n  --tiles=s_[1245678]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        