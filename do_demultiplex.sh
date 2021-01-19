#!/bin/bash
# Run bcl2fastq on <rundir> to <outdir> with <samplesheet> for <lane>.

set -euo pipefail

# Main settings:
RUNDIR="$1"
OUTDIR="$2"
SAMPLESHEET="$3"
LANE="$4"

# bcl2fastq version, and resolve the link if there is one
BCL2FASTQ="$(which bcl2fastq)"
BCL2FASTQ_REAL="$(readlink -f "$BCL2FASTQ")"

echo "RUNDIR=$RUNDIR"
echo "OUTDIR=$OUTDIR"
echo "SAMPLESHEET=$SAMPLESHEET"
echo "LANE=$LANE"
echo "BCL2FASTQ=$BCL2FASTQ"
echo "BCL2FASTQ_REAL=$BCL2FASTQ_REAL"

# We need to strip the other lanes out of the SampleSheet.csv, due to the bug that bcl2fastq
# will do an index collision check for ALL lanes even if you are only trying to process one,
# which breaks the per-lane-base-mask feature.
# This is now done by bcl2fastq_setup.py so no furter filtering is needed.

# Capture the bcl2fastq version
"$BCL2FASTQ" --version 2>&1 | grep . > "$OUTDIR"/bcl2fastq.version

# Get the bcl2fastq section from the SAMPLESHEET.
opts="$( <"$SAMPLESHEET" sed -ne '/^\[bcl2fastq\]/,/^\[/ p' | egrep '^[^[]' )"

# Compile all options in a list
# The 'eval' is needed to convert $LANE to the actual lane number.
opts_list=(-R "$RUNDIR" -o "$OUTDIR")
opts_list+=($(eval echo $opts))
opts_list+=(--sample-sheet "$SAMPLESHEET" -p ${PROCESSING_THREADS:-10})

# See if --barcode-mismatches is in the options at all
if grep -w -- '^--barcode-mismatches' <<<"$opts" ; then
#if printf "%s\n" "${opts_list[@]}" | grep -qFx -- '--barcode-mismatches' ; then

    # --barcode-mismatches is explicitly set

    "$BCL2FASTQ" "${opts_list[@]}" 2> "$OUTDIR"/bcl2fastq.log

    echo "$opts" > "$OUTDIR"/bcl2fastq.opts
else

    # --barcode-mismatches needs to be determined by trial and error

    if ! ( "$BCL2FASTQ" "${opts_list[@]}" --barcode-mismatches 1 2>"$OUTDIR"/bcl2fastq.log && \
            echo "--barcode-mismatches 1" > "$OUTDIR"/bcl2fastq.opts ) ; then

        # Fail due to barcode collision or something else?
        grep -qF 'Barcode collision for barcodes:' "$OUTDIR"/bcl2fastq.log
        mv "$OUTDIR"/bcl2fastq.log "$OUTDIR"/bcl2fastq_mismatch1.log
        "$BCL2FASTQ" "${opts_list[@]}" --barcode-mismatches 0 2>"$OUTDIR"/bcl2fastq.log
        echo "--barcode-mismatches 0" > "$OUTDIR"/bcl2fastq.opts

    fi
    echo "$opts" >> "$OUTDIR"/bcl2fastq.opts
fi
