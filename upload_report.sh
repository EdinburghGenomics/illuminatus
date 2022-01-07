#!/bin/bash
set -euo pipefail

# If you just want to push existing reports to the server, see the RSYNC line below.
# Eg:
#  rsync --rsync-path=bin/rsync_reports -drvlOt multiqc_reports/ \
#      egadmin@egcloud.bio.ed.ac.uk:illuminatus/$(basename $(pwd))/

# See doc/how_to_display.txt for thoughts on how this should really work.
# Normal report destination is https://egcloud.bio.ed.ac.uk/illuminatus

# See where to get the report from (by default, right here)
cd "${1:-.}"
runname="`basename $PWD`"

function echorun(){
    printf $'%q ' "$@" ; printf '\n'
    "$@"
}

# Make a new versioned directory in multiqc_reports and move the reports in there.
# We want to do this even if the actual upload will be skipped.
mkdir -p multiqc_reports/v
nn=0 ; while [[ $nn -lt 9999 ]] ; do
    nn=$(( $nn + 1 ))
    dirtomake=v/`printf $'%04d\n' $nn`
    # This will exit the loop if it successfully makes a new dir.
    if mkdir multiqc_reports/"$dirtomake" ; then
        break
    else
        # Don't keep looping if for some reason the directory is missing but could not be created.
        test -e multiqc_reports/"$dirtomake"
    fi
    dirtomake=NONE
done

# Move the files into this directory. If no files match it's an error.
mv -t multiqc_reports/"$dirtomake" QC/multiqc_*

# Add a symlink to this latest version
ln -sfn "$dirtomake" multiqc_reports/latest

# Add status labels to the directory listing by building an .htaccess file. This is a tad hacky
# in the way it scrapes the reports but given that it's not core to the pipeline I think this is OK.
# An advantage of doing it this way is it will add on labels to existing reports.
( cd multiqc_reports/v ;
  gawk 'BEGIN{print "IndexOptions DescriptionWidth=*"} \
        { if (match($0,"<dt>Pipeline Status:</dt><dd>(.+)</dd>",m) && match(FILENAME,"([^/]+)",f) ) \
          print "AddDescription \""m[1]"\" "f[1] }' \
       */multiqc_report_overview.html \
  > .htaccess )

# Check where (and if) we want to push reports on the server.
if [ "${REPORT_DESTINATION:-none}" == none ] ; then
    echo "Skipping report upload, as no \$REPORT_DESTINATION is set." >&2
    # This will go into RT in place of a link. It's not an error - you can legitimately
    # switch off uploading for testing etc.
    echo '[upload of report was skipped as no REPORT_DESTINATION was set]'
    exit 0
fi
dest="${REPORT_DESTINATION}"

# Allow overriding of RSYNC command. Needed for the setup on egcloud.
# Any required SSH settings should go in ~/.ssh/config
RSYNC_CMD="echorun ${RSYNC_CMD:-rsync}"

echo "Uploading report for $runname to $dest..." >&2
$RSYNC_CMD -drvlOt multiqc_reports/ $dest/$runname/ >&2

# Add the index. We now have to make this a PHP script but at least the content is totally fixed.
index_php="$(dirname $BASH_SOURCE)/templates/index.php"
if $RSYNC_CMD -vp "$index_php" $dest/$runname/ >&2 ; then
    echo "...done. Report uploaded and index.php written to ${dest#*:}/$runname/." >&2
else
    echo "...done. Report uploaded but failed to write index.php to ${dest#*:}/$runname/." >&2
fi

# Say where to find it:
# eg. https://egcloud.bio.ed.ac.uk/illuminatus/...
echo "Link to report is: ${REPORT_LINK:-$REPORT_DESTINATION}/$runname" >&2
echo "${REPORT_LINK:-$REPORT_DESTINATION}/$runname"
