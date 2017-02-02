#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 8 -t 1-3 -q casava -N Ca0811A12345678  -o /ifs/runqc/160811_D00261_0354_AC9J9BANXX/sge_output -e /ifs/runqc/160811_D00261_0354_AC9J9BANXX/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes348_readlen126_index6nnnnnnnnnn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160811_D00261_0354_AC9J9BANXX' -o '/ifs/runqc/160811_D00261_0354_AC9J9BANXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes348_readlen126_index6nnnnnnnnnn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv'   --use-bases-mask Y125n,I6nn,nnnnnnnn,Y125n  --tiles=s_[348]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "2" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_lanes1_readlen126_index8nnnnnnnn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160811_D00261_0354_AC9J9BANXX' -o '/ifs/runqc/160811_D00261_0354_AC9J9BANXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_lanes1_readlen126_index8nnnnnnnn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_forCasava2_17.csv'   --use-bases-mask Y125n,I8,nnnnnnnn,Y125n  --tiles=s_[1]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "3" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_lanes2567_readlen126_index16";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160811_D00261_0354_AC9J9BANXX' -o '/ifs/runqc/160811_D00261_0354_AC9J9BANXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_lanes2567_readlen126_index16' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_forCasava2_17.csv'   --use-bases-mask Y125n,I8,I8,Y125n  --tiles=s_[2567]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        