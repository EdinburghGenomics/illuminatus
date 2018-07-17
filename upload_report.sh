#!/bin/bash
set -euo pipefail

# If you just want to push existing reports to the server, see the RSYNC line below.
# Eg:
#  rsync -drvlOt multiqc_reports/ web1.genepool.private:/var/runinfo/illuminatus_reports/test/$(basename $(pwd))/

# See doc/how_to_display.txt for thoughts on how this should really work.
# Normal report destination is web1.genepool.private:/var/runinfo/illuminatus_reports

# See where to get the report from (by default, right here)
cd "${1:-.}"
runname="`basename $PWD`"

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

# Check where (and if) we want to push reports on the server.
if [ "${REPORT_DESTINATION:-none}" == none ] ; then
    echo "Skipping report upload, as no \$REPORT_DESTINATION is set." >&2
    # This will go into RT in place of a link. It's not an error - you can legitimately
    # switch off uploading for testing etc.
    echo '[upload of report was skipped as no REPORT_DESTINATION was set]'
    exit 0
fi
dest="${REPORT_DESTINATION}"

# Note the proxy setting in my ~/.ssh/config which lets both ssh
# and rsync run through monitor transparently. Really we should have direct access to the
# DMZ machines.
echo "Uploading report for $runname to $dest..." >&2
rsync -drvlOt multiqc_reports/ $dest/$runname/ >&2

# Add the index. We now have to make this a PHP script but at least the content is totally fixed.
ssh ${dest%%:*} "cat > ${dest#*:}/$runname/index.php" <<'END'
<?php
    # Script added by upload_report.sh in Illuminatus.
    # First resolve symlink. The subtlety here is that anyone saving the link will get a permalink,
    # and anyone just reloading the page in their browser will see the old one. I think that's
    # OK. It's easy to change in any case.
    $latest = readlink("latest");
    # Get the url and slice off index.php and/or / if found. No, I'm not fluent in PHP!
    $myurl = strtok($_SERVER["REQUEST_URI"],'?');
    if( preg_match('/' . basename(__FILE__) . '$/', $myurl )){
        $myurl = substr( $myurl, 0, -(strlen(basename(__FILE__))) );
    }
    if( preg_match(',/$,', $myurl )){
        $myurl = substr( $myurl, 0, -1 );
    }
    header("Location: $myurl/$latest/multiqc_report_overview.html", true, 302);
    exit;
?>
<html>
<head>
<title>Redirect</title>
<meta name="robots" content="none" />
</head>
<body>
   You should be redirected to <a href='latest/multiqc_report_overview.html'>latest/multiqc_report_overview.html</a>
</body>
</html>
END

# For stuff already uploaded we have an index.html symlink which must be (cautiously) removed.
# TODO - remove this in a month or so when there's no danger of a clash.
ssh ${dest%%:*} "[ ! -L ${dest#*:}/$runname/index.html ] || rm ${dest#*:}/$runname/index.html"

echo "...done. Report uploaded and index.php written to ${dest#*:}/$runname/." >&2

# Say where to find it:
# eg. http://web1.genepool.private/runinfo/illuminatus_reports/...
echo "${REPORT_LINK:-$REPORT_DESTINATION}/$runname"
