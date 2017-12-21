#!/bin/bash
set -euo pipefail

# See doc/how_to_display.txt for thoughts on how this should really work.
# Normal report destination is web1.genepool.private:/var/runinfo/illuminatus_reports

# Push reports onto the server.
if [ "${REPORT_DESTINATION:-none}" == none ] ; then
    echo "Skipping report upload, as no \$REPORT_DESTINATION is set." >&2
    echo "[upload of report was skipped]"
fi
dest="${REPORT_DESTINATION}"

# See where to get the report from (by default, right here)
cd "${1:-.}"
runname="`basename $PWD`"

# Note the proxy setting in my ~/.ssh/config which lets both ssh
# and rsync run through monitor transparently.
echo "Uploading report for $runname to $dest..." >&2
rsync -drvl --include='multiqc_*' --exclude='*' QC/ $dest/$runname/ >&2

# Add the index.
ssh ${dest%%:*} ln -svf multiqc_report_overview.html ${dest#*:}/$runname/index.html >&2
echo "...done. Report loaded and linked." >&2

# Say where to find it:
# eg. http://web1.genepool.private/runinfo/illuminatus_reports/...
echo "${REPORT_LINK:-$REPORT_DESTINATION}/$runname"
