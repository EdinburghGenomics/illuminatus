#!/usr/bin/env python3
import os, sys, re
from glob import glob
from shutil import rmtree
import time

def main(output_dir, *lanes):
    """Usage: BCL2FASTQCleanup.py <output_dir> <lanes_list>

    Given an output folder, clean up old FASTQ files ready for re-demultiplexing.
    Also clean [other stuff]. See design criteria at:
      https://www.wiki.ed.ac.uk/pages/viewpage.action?pageId=319660973

    Also see the unit tests (as always)
    """

    output_dir = os.path.abspath(output_dir)

    # Open the log. This will barf on non-existent output_dir.
    with open(os.path.join(output_dir, 'cleanup.log'), 'a') as log_fh:
        log = lambda m: print(m, file=log_fh)
        die = lambda m: print("# ERROR: %s" % m, file=log_fh) or exit(m)

        log("# %s" % sys.argv[0])
        log("# cleaning lanes %s in %s on %s" % (
                              lanes,
                                 output_dir,
                                       time.strftime('%Y-%m-%d %H:%M', time.localtime()) ))

        # Sanity checking...
        if not lanes:
            die("No lanes specified to process.")

        for l in lanes:
            if l not in list("12345678"):
                die("%s is not a valid lane." % l)

        # Collector for projects removed
        projects = set()
        lanes = set(lanes)

        try:
            # Deleting the FASTQ that hasn't been renamed
            projects.update(delete_d_dirs(os.path.join(output_dir, 'demultiplexing'), lanes, log=log))

            # Deleting the FASTQ that is already post-processed
            projects.update(delete_p_fastq(output_dir, lanes, log=log))

            # Deleting the [other stuff]
            # md5sums and counts are removed by the 'otherdirs' option passed to delete_fastq.
            # We should also scrub the QC? Stale info in the MultiQC reports will be bad!!
            del_qc = "rm -rf {od}/QC/lane[{l}] {od}/QC/multiqc_report_lane[{l}]*".format(l=''.join(lanes), od=output_dir)
            os.system(del_qc)
            log(del_qc)

            # Put anything I deleted into projects_pending.txt
            with open(os.path.join(output_dir, 'projects_pending.txt'), 'a') as pp_fh:
                for p in projects:
                    print(p, file=pp_fh)

                log("# DONE: %s projects added to projects_pending.txt" % len(projects))


        except BaseException as e:
            # Trap BaseException so we log death-by-SIGINT
            log("# EXCEPTION: %s" % e)
            raise

def delete_p_fastq(path, lanes, **kwargs):
    """Delete FASTQ from the top-level dir and return a list of the projects
       impacted.
       Files in here match [0-9]{6}_[^_]+_[0-9]+_[^_]+_(.)_[^_]+_[1234u]\.fastq\.gz
       where $1 is the lane number.
    """
    return delete_fastq( path, lanes,
                         re.compile(r'^[0-9]{6}_[^_]+_[0-9]+_[^_]+_(.)_[^_]+_(?:[0-9]|UMI)\.fastq\.gz'),
                         otherdirs=('md5sums', 'counts'),
                         **kwargs )


def delete_d_fastq(path, lanes, **kwargs):
    """Delete FASTQ from the demultiplexing area and return a list of the projects
       impacted.
       Files in here match .*_L00(.)_.\d_\d\d\d\.fastq\.gz where $1 is the lane.
    """
    return delete_fastq( path, lanes,
                         re.compile(r'_L00(.)_.._\d\d\d\.fastq\.gz$'),
                         **kwargs )

def delete_d_dirs(path, lanes, log=lambda x: None):
    """I was using delete_d_fastq to prune out individual FASTQ files, but now I just
       want to delete entire directories: path/lane?
    """
    projects = set()
    deletions = 0
    for lane in lanes:
        lane_dir = os.path.join(path, "lane%s" % lane)

        # There may not be a directory to delete.
        if not os.path.exists(lane_dir):
            continue

        proj_in_lane = [ os.path.basename(d) for d in
                         glob(os.path.join(lane_dir, '[0-9]*')) ]

        projects.update(proj_in_lane)

        # Delete whole directory. If bcl2fastq completed this is just the logs.
        log("rm -r '%s'" % lane_dir)
        rmtree(lane_dir)
        deletions += 1

    msg = "Deleted %i directories complete with files relating to %i projects." % (
                   deletions,                                     len(projects) )
    log('# ' + msg)
    return projects

def delete_fastq(path, lanes, match_pattern, log=lambda x: None, otherdirs=()):
    """Generic file deleter given a path and a pattern.
    """
    # Find all the matching files. Here we have a baked-in idea of what a project number
    # should look like, so if this changes the code will have to change.
    ppatterns = ['[0-9]+', 'ControlLane']

    projects = set()
    deletions = list()
    od_deletions = 0
    emptydirs = 0
    for root, dirs, files in os.walk(path):
        # At the top level, only descent into directories that are numbers (ie. projects),
        # or 'ControlLane' as a special case.
        # We expect to see the unassigned reads at this level
        if root == path:
            dirs[:] = [ d for d in dirs if any(re.search('^{}$'.format(p), d) for p in ppatterns) ]

        for f in files:
            mo = re.search(match_pattern, f)
            if mo and mo.group(1) in lanes:
                # Pull out the project from the path (unassigned files have no project, of course!)
                proj = root[len(path):].strip(os.path.sep).split(os.path.sep)[0]
                if proj: projects.add( proj )

                os.remove(os.path.join(root, f))
                log( "rm '{}'".format(os.path.join(root, f)) )
                deletions.append(os.path.join(root[len(path):], f))

        # Useful for debugging
        #    else:
        #        if mo:
        #            log("# lane %s is not in %s" % (mo.group(1), lanes))
        #        else:
        #            log("# %s does not match %s" % (f, match_pattern))

    # Deal with otherdirs - ie places where supplementary files lurk.
    # We're looking for files with a matching name, but a different extension.
    for od in otherdirs:
        for f in deletions:
            for odf in glob( "{}/{}/{}.*".format(path, od, f.split('.')[0]) ):
                os.remove(odf)
                log( "rm '{}'".format(odf) )
                od_deletions += 1


    # Now remove empty directories. We only want to look at those in projects.
    for proj in projects:
        for root, dirs, files in os.walk(os.path.join(path, proj), topdown=False):
            try:
                os.rmdir(root)
                log("rmdir '%s'" % root)
                emptydirs += 1
            except Exception:
                pass # Assume it was non-empty.

    msg = "Deleted {} fastq files and {} ancillary files and {} directories from {} relating to {} projects.".format(
                   len(deletions),    od_deletions,          emptydirs, os.path.basename(path), len(projects) )
    log('# ' + msg)
    #print(msg)
    return projects

if __name__ == '__main__':
    print("Running " + ' '.join(sys.argv))
    main(*sys.argv[1:])
