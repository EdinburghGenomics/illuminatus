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
