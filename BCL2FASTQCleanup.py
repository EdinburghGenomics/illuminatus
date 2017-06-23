#!/usr/bin/env python3
import os, sys, re
from glob import glob
import time

def main(output_dir, *lanes):
    """Usage: BCL2FASTQCleanup.py <output_dir> <lanes_list>

    Given an output folder, clean up old FASTQ files ready for re-demultiplexing.
    Also clean [other stuff]. See design criteria at:
      https://genowiki.is.ed.ac.uk/pages/viewpage.action?pageId=319660973
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
            projects.update(delete_d_fastq(os.path.join(output_dir, 'demultiplexing'), lanes, log=log))

            # Deleting the FASTQ that is already post-processed
            projects.update(delete_p_fastq(output_dir, lanes, log=log))

            # Deleting the [other stuff]
            pass

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
       Files in here match [0-9]{6}_[^_]+_[0-9]+_[^_]+_(.)_[^_]+(_[12]|)\.fastq\.gz
       where $1 is the lane number.
    """
    return delete_fastq( path, lanes,
                         re.compile(r'^[0-9]{6}_[^_]+_[0-9]+_[^_]+_(.)_[^_]+(_[12]|)\.fastq\.gz'),
                         **kwargs )


def delete_d_fastq(path, lanes, **kwargs):
    """Delete FASTQ from the demultiplexing area and return a list of the projects
       impacted.
       Files in here match .*_L00(.)_.\d_\d\d\d\.fastq\.gz where $1 is the lane.
    """
    return delete_fastq( path, lanes,
                         re.compile(r'_L00(.)_.._\d\d\d\.fastq\.gz$'),
                         **kwargs )


def delete_fastq(path, lanes, match_pattern, log=lambda x: None):
    """Generic file deleter given a path and a pattern.
    """
    # Find all the matching files. Simplistically, assume that any top-level directory
    # that contains such files is a project number.
    projects = set()
    deletions = 0
    emptydirs = 0
    for root, dirs, files in os.walk(path):
        # At the top level, only descent into directories that are numbers (ie. projects)
        # We expect to see the unassigned reads at this level
        if root == path:
            dirs[:] = [ d for d in dirs if re.search(r'^[0-9]+$', d) ]

        for f in files:
            mo = re.search(match_pattern, f)
            if mo and mo.group(1) in lanes:
                # Pull out the project from the path (unassigned files have no project, of course!)
                proj = root[len(path):].strip(os.path.sep).split(os.path.sep)[0]
                if proj: projects.add( proj )

                os.remove(os.path.join(root, f))
                log("rm '%s'" % os.path.join(root, f))
                deletions += 1

        # Useful for debugging
        #    else:
        #        if mo:
        #            log("# lane %s is not in %s" % (mo.group(1), lanes))
        #        else:
        #            log("# %s does not match %s" % (f, match_pattern))

    # Now remove empty directories. We only want to look at those in projects.
    for proj in projects:
        for root, dirs, files in os.walk(os.path.join(path, proj), topdown=False):
            try:
                os.rmdir(root)
                log("rmdir '%s'" % root)
                emptydirs += 1
            except Exception:
                pass # Assume it was non-empty.

    msg = "Deleted %i files and %i directories from %s relating to %i projects." % (
                   deletions,   emptydirs,  os.path.basename(path), len(projects) )
    log('# ' + msg)
    print(msg)
    return projects

if __name__ == '__main__':
    main(*sys.argv[1:])
