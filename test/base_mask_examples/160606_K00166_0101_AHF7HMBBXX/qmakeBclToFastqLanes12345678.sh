#!/bin/bash
#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe casava 8 -t 1-3 -q casava -N Ca0606A12345678  -o /ifs/runqc/160606_K00166_0101_AHF7HMBBXX/sge_output -e /ifs/runqc/160606_K00166_0101_AHF7HMBBXX/sge_output

echo $PWD
printenv
echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes34578_readlen76_index6nnnnnnnnnn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160606_K00166_0101_AHF7HMBBXX' -o '/ifs/runqc/160606_K00166_0101_AHF7HMBBXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_lanes34578_readlen76_index6nnnnnnnnnn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_6_forCasava2_17.csv'   --use-bases-mask Y75n,I6nn,nnnnnnnn,Y75n  --tiles=s_[34578]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "2" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_lanes12_readlen76_index8nnnnnnnn";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160606_K00166_0101_AHF7HMBBXX' -o '/ifs/runqc/160606_K00166_0101_AHF7HMBBXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_lanes12_readlen76_index8nnnnnnnn' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_8_forCasava2_17.csv'   --use-bases-mask Y75n,I8,nnnnnnnn,Y75n  --tiles=s_[12]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        
        if [ "$SGE_TASK_ID" -eq "3" ]; then
          echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_lanes6_readlen76_index16";
          /ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/bcl2fastq -R '/ifs/seqdata/160606_K00166_0101_AHF7HMBBXX' -o '/ifs/runqc/160606_K00166_0101_AHF7HMBBXX/Unaligned_SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_lanes6_readlen76_index16' --sample-sheet 'SampleSheet_in_HiSeq_format_removedDummyIndexes_indexLength_16_forCasava2_17.csv'   --use-bases-mask Y75n,I8,I8,Y75n  --tiles=s_[6]  --barcode-mismatches 1  --fastq-compression-level 6  ;
        fi
        