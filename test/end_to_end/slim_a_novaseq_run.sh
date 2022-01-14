#!/bin/bash
set -ue

# Takes a run folder and makes a mini version of it for you to test on.
# eg:
# $ test/end_to_end/slim_a_novaseq_run.sh 180412_A00291_0020_BH2YTVDRXX ~/test_seqdata
# Because NovaSeq runs bunch all the data together in .cbcl files we can't prune
# them down in the same way. My solution is to make hard links, so the data will
# be the same but by only working on a single tile it will still be quick to
# process.

RUN_PATH="${1:?Give me a run to slim}"
DEST="${2:-.}"

# If RUN_ID contains no /, assume /lustre/seqdata
# You can slim direct from /ifs/seqdata but you need to be explicit.
if [[ ! "$RUN_PATH" =~ / ]] ; then
    RUN_PATH=/lustre-gseg/seqdata/"$RUN_PATH"
fi
RUN_ID="`basename $RUN_PATH`"

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
    cp "$RUN_PATH/$p"/* "$DEST/$p" 2>/dev/null || true
done

# Now make some links
for lane in $LANES ; do
  ln -snrv -t "$DEST"/Data/Intensities/BaseCalls/$lane/ "$RUN_PATH"/Data/Intensities/BaseCalls/$lane/s_*_2101.filter

  CYCLES="`ls "$RUN_PATH"/Data/Intensities/BaseCalls/$lane | grep -x 'C[0-9]\+.1'`"
  echo "Linking `wc -w <<<$CYCLES` cyles of bcl[.gz] files for side 2 of $lane..."
  for cycle in $CYCLES ; do
    mkdir "$DEST"/Data/Intensities/BaseCalls/$lane/$cycle
    ln -snrv -t "$DEST"/Data/Intensities/BaseCalls/$lane/$cycle/ "$RUN_PATH"/Data/Intensities/BaseCalls/$lane/$cycle/*_2.cbcl
  done
done

# Copy most of the InterOp files. I think we only need the top-level ones.
echo "Copying InterOp files, excluding RegistrationMetricsOut, EventMetricsOut and FWHMGridMetricsOut"
mkdir -p "$DEST"/InterOp
for f in "$RUN_PATH"/InterOp/* ; do
    do_copy=1
    for x in RegistrationMetricsOut EventMetricsOut FWHMGridMetricsOut ; do
        [ "`basename $f .bin`" == "$x" ] && do_copy=0
    done
    [ "$do_copy" = 1 ] && [ -f "$f" ] && cp "$f" "$DEST"/InterOp
done

# Make a pipeline_settings.ini file telling blc2fastq to ignore the missing tiles
# Note this assumes if pipeline_settings.ini exists already it only has a [bcl2fastq] section, most
# likely overriding --barcode-mismatches.
if [ ! -e "$DEST"/pipeline_settings.ini ] ; then
    echo "[bcl2fastq]" > "$DEST"/pipeline_settings.ini
fi
echo '--tiles: "s_[$LANE]_2101"' >> "$DEST"/pipeline_settings.ini

# Finally, if it's already a link, copy the SampleSheet.csv to SampleSheet.csv.OVERRIDE
# so it can be edited and Illuminatus won't try to replace it.
if [ -L "$DEST"/SampleSheet.csv ] ; then
    echo Creating "$DEST"/SampleSheet.csv.OVERRIDE
    cat "$DEST"/SampleSheet.csv > "$DEST"/SampleSheet.csv.OVERRIDE
fi

echo DONE
