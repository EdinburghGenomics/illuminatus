#!/usr/bin/env python3

"""
    "Fixes" the output of bcl2fastq to meet our requirements - mostly regarding file names.
    Folder structure is left unmolested.
    projects_ready.txt is added listing the projects found
    projects_pending.txt is deleted if it exists
"""
# FIXME - I think we should be moving the files from demultiplexing into the root dir.
# In which case this script wants to be run in the top-level directory.
# I guess we could go back to keeping the files in /ifs/runqc until they are renamed,
# and this might be sensible for backup purposes. In any case I could do this with a
# symlink so the code can stay the same.

import os, sys, re, time
from glob import glob

def main(output_dir, prefix=None):
    """ Usage BCL2FASTQPostprocessor.py <run_dir> [prefix]
    """
    output_dir = os.path.abspath(output_dir)

    #The prefix is normally the run name ie. the folder name, but driver.sh
    #will set this explicitly based on RunInfo.
    if not prefix:
        prefix = os.path.basename(output_dir)

    #All renames need to be logged. The log wants to live in the demultiplexing/
    #subdirectory.
    demux_dir = output_dir + "/demultiplexing"
    with open(os.path.join(demux_dir, 'renames.log'), 'a') as log_fh:
        log = lambda m: print(m, file=log_fh)
        log("# %s" % sys.argv[0])
        log("# renaming files in %s on %s" % (
                                 demux_dir,
                                       time.strftime('%Y-%m-%d %H:%M', time.localtime()) ))

        project_list = do_renames(output_dir, prefix, log=log)

        save_projects_ready(output_dir, project_list)

        log("# DONE. And projects_ready.txt was saved out.")


def save_projects_ready(output_dir, project_list):
    """Save out what we've processed. There might be stuff already in projects_ready.txt
       and we want to maintain the contents as a sorted set (as per 'sort -u')
    """
    proj_seen = set(project_list)

    proj_ready_file = os.path.join(output_dir, 'projects_ready.txt')
    try:
        with open(proj_ready_file) as pr_fh:
            for l in pr_fh:
                proj_seen.add(l.strip())
    except FileNotFoundError:
        # OK, there was no old file
        pass

    with open(proj_ready_file, 'w') as pr_fh:
        for p in sorted(proj_seen):
            print(p, file=pr_fh)

    # And delete projects_pending.txt. It probably doesn't exist, which is fine.
    try:
        os.unlink(os.path.join(output_dir, 'projects_pending.txt'))
    except FileNotFoundError:
        pass

def do_renames(output_dir, prefix, log = lambda m: print(m)):
    """ The main part of the code that does the renaming (moving).
        Primary reason for splitting this out from main() is to separate
        the sys.argv processing and the log file handling in order to
        simplify unit testing.
        Returns the list of projects for which files have been renamed.
    """
    proj_seen = []

    # No attempt to define what directories are 'project' directories, aside from looking
    # for those that contain FASTQ files at the right level.
    for fastq_file in glob(os.path.join( output_dir, "demultiplexing" , "*/*/*.fastq.gz" )):

        #os.path.split is unhelpful here. Just do it the obvious way.
        # something like: 10528, 10528EJ0019L01, 10528EJpool03_S19_L005_R1_001.fastq.gz
        project, library, filename = fastq_file.split('/')[-3:]
        fastq_path = os.path.join(project, library)

        # get information from the filename
        re_match = re.match( r'(.*)_(.*)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping %s" % fastq_file)
            continue
        pool = re_match.group(1) # e.g.: 10528EJpool03
        lane = re_match.group(3) # e.g.: L00(5)
        readnumber = re_match.group(4) # e.g.: R(1)

        new_filename = "{prefix}_{lane}_{library}_{readnumber}.fastq.gz".format(**locals())
        new_filename_absolute = os.path.join ( output_dir, fastq_path, new_filename )

        #Make the directory to put it in
        os.makedirs(os.path.dirname(new_filename_absolute), exist_ok=True)

        #Paranoia. Rather than checking if the file exists, create it exclusively.
        #That way, no possible race condition that can cause one file to be renamed over
        #another file.
        with open(new_filename_absolute, 'x') as tmp_fd:
            fastq_file_relative = os.path.join("demultiplexing", fastq_path, filename)
            new_filename_relative = os.path.join ( fastq_path, new_filename )
            log( "mv %s %s" % (fastq_file_relative, new_filename_relative) )

            os.replace(fastq_file, new_filename_absolute)

        #Only if we actually renamed a file, note the project as one we've processed.
        proj_seen.append(project)

    # Now deal with the undetermined files.
    for undet_file_absolute in glob(os.path.join( output_dir, "demultiplexing", "[Uu]ndetermined_*" )):
        filename = undet_file_absolute.split('/')[-1]

        # eg. Undetermined_S0_L004_R1_001.fastq.gz
        re_match = re.match( r'undetermined_(.*)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping %s" % fastq_file)
            continue

        lane = re_match.group(2)
        readnumber = re_match.group(3)

        # eg. 160811_D00261_0355_BC9DA7ANXX_4_unassigned_1.fastq.gz
        new_filename = "{prefix}_{lane}_unassigned_{readnumber}.fastq.gz".format(**locals())

        new_filename_absolute = os.path.join ( output_dir, new_filename )

        #See comment above
        with open(new_filename_absolute, 'x') as tmp_fd:
            log( "mv %s %s" % ( os.path.join("demultiplexing", filename), new_filename) )
            os.rename(undet_file_absolute, new_filename_absolute)

    # If the sample sheet is wrongly formatted, we'll get .fastq.gz files appearing one level up.
    # Detect these and log.
    for wrong_level_file in glob(os.path.join( output_dir, "demultiplexing" , "*/*.fastq.gz" )):
        project, filename = wrong_level_file.split('/')[-2:]
        log( "# project %s contains unexpected file %s" % (project, filename) )

    # Cleanup empty project directories (as per Cleanup.py) then warn if any dirs
    # remain (maybe the warning should be more like an error?).
    for proj in set(proj_seen):
        for root, dirs, files in os.walk(
                                     os.path.join(output_dir, "demultiplexing", proj),
                                     topdown=False ):
            try:
                os.rmdir(root)
                log("rmdir '%s'" % root)
            except Exception:
                # Assume it was non-empty.
                log("# could not remove dir '%s'" % root)

    # Finally return the projects processed
    return proj_seen

if __name__ == '__main__':
    main(*sys.argv[1:])
