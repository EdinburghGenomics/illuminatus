#!/bin/bash
set -ue

# Takes a run folder and makes a mini version of it for you to test on.
RUN_ID="${1:?Give me a run to slim}"
DEST="${2:-.}"

# If RUN_ID contains no /, assume /lustre/seqdata
if [[ ! "$RUN_ID" =~ / ]] ; then
    RUN_ID=/lustre/seqdata/"$RUNID"
fi

# Now DEST...
DEST="$DEST/`basename $RUN_ID`"

echo "Slimming down $RUN_ID --> $DEST"
exit 1
mkdir /ifs/runqc/test_seqdata/$RUN_ID/
mkdir /ifs/runqc/test_seqdata/$RUN_ID/Data/
mkdir /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/
mkdir /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/BaseCalls/
mkdir /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/BaseCalls/L00{1,2,3,4,5,6,7,8}
cp /ifs/seqdata/$RUN_ID/* /ifs/runqc/test_seqdata/$RUN_ID/
cp /ifs/seqdata/$RUN_ID/Data/* /ifs/runqc/test_seqdata/$RUN_ID/Data
cp /ifs/seqdata/$RUN_ID/Data/Intensities/* /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/
cp /ifs/seqdata/$RUN_ID/Data/Intensities/BaseCalls/* /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/BaseCalls/

LANE=1; 
for LANE in $(seq 1 8); do \
  cp /ifs/seqdata/$RUN_ID/Data/Intensities/BaseCalls/L00$LANE/s_${LANE}_1101.filter /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/BaseCalls/L00$LANE/; \
    for f in $(seq 1 310); do \
        mkdir /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/BaseCalls/L00$LANE/C$f.1; \
            cp /ifs/seqdata/$RUN_ID/Data/Intensities/BaseCalls/L00$LANE/C$f.1/s_${LANE}_1101.bcl.gz /ifs/runqc/test_seqdata/$RUN_ID/Data/Intensities/BaseCalls/L00$LANE/C$f.1/s_${LANE}_1101.bcl.gz; done ;done

