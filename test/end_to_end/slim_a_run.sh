#!/bin/bash
set -ue

# Takes a run folder and makes a mini version of it for you to test on.
# eg:
# $ test/end_to_end/slim_a_run.sh 170221_K00166_0183_AHHT3HBBXX ~/test_seqdata

RUN_PATH="${1:?Give me a run to slim}"
DEST="${2:-.}"

# If RUN_ID contains no /, assume /lustre/seqdata
# You can slim direct from /ifs/seqdata but you need to be explicit.
if [[ ! "$RUN_PATH" =~ / ]] ; then
    RUN_PATH=/lustre-gseg/seqdata/"$RUN_PATH"
fi
RUN_ID="`basename $RUN_PATH`"

if [[ "$RUN_ID" =~ _A00 ]] ; then
    echo 'Looks like a NovaSeq run. Use slim_a_novaseq_run.sh instead!'
    exit 1
fi

# Now DEST...
DEST="$DEST/$RUN_ID"

if [ -e "$DEST" ] ; then
  echo "$DEST already exists. Remove it first."
  exit 1
fi

echo "Slimming down $RUN_PATH --> $DEST"

LANES="`ls "$RUN_PATH"/Data/Intensities/BaseCalls | grep -x L...`"
echo "Making directories for `wc -w <<<$LANES` lanes."
for lane in $LANES ; do
    mkdir -p "$DEST"/Data/Intensities/BaseCalls/$lane
done

# Copy files, but not folders, at various levels
for p in . Data Data/Intensities Data/Intensities/BaseCalls ; do
    echo "Copying all regular files from $RUN_PATH/$p"
    cp -P -t "$DEST/$p" "$RUN_PATH/$p"/* 2>/dev/null || true
done

for lane in $LANES ; do
  cp -v "$RUN_PATH"/Data/Intensities/BaseCalls/$lane/s_*_1101.filter "$DEST"/Data/Intensities/BaseCalls/$lane/
  #Only for MiSeq machines I think
  cp -v "$RUN_PATH"/Data/Intensities/BaseCalls/$lane/s_*_1101.control "$DEST"/Data/Intensities/BaseCalls/$lane/ || true
  #For non-patterned machines where there is a .locs (or .clocs) file per-tile
  if [ -e "$RUN_PATH"/Data/Intensities/$lane ] ; then
    mkdir -p "$DEST"/Data/Intensities/$lane/
    cp -v "$RUN_PATH"/Data/Intensities/$lane/s_*_1101.*locs "$DEST"/Data/Intensities/$lane/
  fi

  CYCLES="`ls "$RUN_PATH"/Data/Intensities/BaseCalls/$lane | grep -x 'C[0-9]\+.1'`"
  echo "Copying `wc -w <<<$CYCLES` cyles of bcl[.gz] files for tile 1101 of $lane..."
  for cycle in $CYCLES ; do
    mkdir "$DEST"/Data/Intensities/BaseCalls/$lane/$cycle
    cp "$RUN_PATH"/Data/Intensities/BaseCalls/$lane/$cycle/s_*_1101.bcl* "$DEST"/Data/Intensities/BaseCalls/$lane/$cycle/
    #We may or may not have these files
    cp "$RUN_PATH"/Data/Intensities/BaseCalls/$lane/$cycle/s_*_1101.stats "$DEST"/Data/Intensities/BaseCalls/$lane/$cycle/ 2>/dev/null || true
  done
done

# Copy most of the InterOp files
echo "Copying InterOp files, excluding RegistrationMetricsOut, EventMetricsOut and FWHMGridMetricsOut"
mkdir -p "$DEST"/InterOp
for f in "$RUN_PATH"/InterOp/* ; do
    do_copy=1
    for x in RegistrationMetricsOut EventMetricsOut FWHMGridMetricsOut ; do
        [ "`basename $f .bin`" == "$x" ] && do_copy=0
    done
    [ "$do_copy" = 1 ] && cp $f "$DEST"/InterOp
done

# Make a pipeline_settings.ini file telling blc2fastq to ignore the missing tiles
# Note this assumes if pipeline_settings.ini exists already it only has a [bcl2fastq] section, most
# likely overriding --barcode-mismatches.
if [ ! -e "$DEST"/pipeline_settings.ini ] ; then
    echo "[bcl2fastq]" > "$DEST"/pipeline_settings.ini
fi
echo '--tiles: s_[$LANE]_1101' >> "$DEST"/pipeline_settings.ini

# Finally, if it's already a link, copy the SampleSheet.csv to SampleSheet.csv.XOVERRIDE
# so it can be edited and Illuminatus won't try to replace it. This can't be in the pipeline
# directory since the pipeline needs to create that.
if [ -L "$RUN_PATH/SampleSheet.csv" ] ; then
    echo Creating "$DEST/SampleSheet.csv.XOVERRIDE"
    cat "$RUN_PATH/SampleSheet.csv" > "$DEST/SampleSheet.csv.XOVERRIDE"
    ( cd "$DEST" && ln -snf SampleSheet.csv.XOVERRIDE SampleSheet.csv )
fi

echo DONE
