#!/bin/bash
# Run bcl2fastq on {{runid}} lane {{lane}}.

set -euo pipefail

# You are either looking at the template used by BCL2FASTQPreprocessor.py or else a
# script made from the template. See templates/do_demultiplex.sh.ms for the original.

# Main settings:
echo BCL2FASTQ={{bcl2fastq}}
echo INPATH={{rundir}}
echo SAMPLESHEET={{samplesheet}}
echo OUTPATH={{destdir}}/lane{{lane}}

INPATH={{rundir}}
OUTPATH={{destdir}}/lane{{lane}}

# We need to strip the other lanes out of the SampleSheet.csv, due to the bug that bcl2fastq
# will do an index collision check for ALL lanes even if you are only trying to process one,
# which breaks the per-lane-base-mask feature.
# We can do this munging on the fly (this assuming we never see more than 8 lanes)...
LANE={{lane}}
SHEET_FILTER="`tr -d {{lane}} <<<'^[12345678],'`"

{{bcl2fastq}} --version 2> "$OUTPATH"/bcl2fastq.version

{{#barcode_mismatches}}
# --barcode-mismatches explicitly set to {{barcode_mismatches}}
{{bcl2fastq}} -R "$INPATH" -o "$OUTPATH" {{#bcl2fastq_opts}}{{{.}}} {{/bcl2fastq_opts}} \
    --sample-sheet <(grep -v "$SHEET_FILTER" {{samplesheet}}) -p ${PROCESSING_THREADS:-10} \
    2> "$OUTPATH"/bcl2fastq.log && \
echo --barcode-mismatches 0 > "$OUTPATH"/bcl2fastq.opts

{{/barcode_mismatches}}
{{^barcode_mismatches}}
# --barcode-mismatches needs to be determined by trial and error

if ! ( {{bcl2fastq}} -R "$INPATH" -o "$OUTPATH" {{#bcl2fastq_opts}}{{{.}}} {{/bcl2fastq_opts}} \
            --sample-sheet <(grep -v "$SHEET_FILTER" {{samplesheet}}) -p ${PROCESSING_THREADS:-10} --barcode-mismatches 1 \
            2> "$OUTPATH"/bcl2fastq.log && \
       echo --barcode-mismatches 1 > "$OUTPATH"/bcl2fastq.opts ) ; then
    # Fail due to barcode collision or something else?
    if grep -qF 'Barcode collision for barcodes:' "$OUTPATH"/bcl2fastq.log ; then
        mv "$OUTPATH"/bcl2fastq.log "$OUTPATH"/bcl2fastq_mismatch1.log
        {{bcl2fastq}} -R "$INPATH" -o "$OUTPATH" {{#bcl2fastq_opts}}{{{.}}} {{/bcl2fastq_opts}} \
            --sample-sheet <(grep -v "$SHEET_FILTER" {{samplesheet}}) -p ${PROCESSING_THREADS:-10} --barcode-mismatches 0 \
            2> "$OUTPATH"/bcl2fastq.log && \
        echo --barcode-mismatches 0 > "$OUTPATH"/bcl2fastq.opts
    else
        # Failure
        false
    fi
fi
{{/barcode_mismatches}}
