#!/usr/bin/env python3

"""
    "Fixes" the output of bcl2fastq to meet our requirements - mostly regarding file names.
    Folder structure is left unmolested.
    projects_ready.txt is added listing the projects found
    projects_pending.txt is deleted if it exists
"""
import os, sys, glob, re, time

def main():
    """ Usage BCL2FASTQPostprocessor.py <run_dir> [prefix]
    """
    demux_folder = sys.argv[1]

    #The prefix is normally the run name ie. the foilder name.
    prefix = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(demux_folder)

    #All renames need to be logged
    with open(os.path.join(demux_folder, 'renames.log'), 'a') as log_fh:
        log = lambda m: print(m, file=log_fh)
        log("# %s renaming files in %s on %s" % (
               sys.argv[0],             demux_folder,
                                          time.strftime('%Y-%m-%d %H:%M', time.localtime()) ))

        project_list = do_renames(demux_folder, prefix, log=log)

        save_projects_ready(demux_folder, project_list)

        log("# DONE. And projects_ready.txt was saved out.")


def save_projects_ready(demux_folder, project_list):
    #Save out what we've processed. There might be stuff already in projects_ready.txt
    #and we want to maintain the contents as a sorted set (as per 'sort -u')
    proj_seen = set(project_list)

    proj_ready_file = os.path.join(demux_folder, 'projects_ready.txt')
    try:
        with open(proj_ready_file) as pr_fh:
            for l in pr_fh:
                proj_seen.add(l.strip())
    except FileNotFoundError:
        pass

    with open(proj_ready_file, 'w') as pr_fh:
        for p in sorted(proj_seen):
            print(p, file=pr_fh)

    # And delete projects_pending.txt. It probably doesn't exist, which is fine.
    try:
        os.unlink(os.path.join(demux_folder, 'projects_pending.txt'))
    except FileNotFoundError:
        pass


def do_renames(demux_folder, prefix, log = lambda m: print(m)):
    """ The main part of the code that does the renaming.
        Primary reason for splitting this out from main() is to separate
        the sys.argv processing and the log file handling in order to
        simplify unit testing.
        Returns the list of projects for which files have been renamed.
    """
    proj_seen = []

    demux_folder_content = glob.glob( os.path.join( demux_folder , "?????/*/*" ) )

    for fastq_file in demux_folder_content:

        #os.path.split is unhelpful here. Just do it the obvious way.
        split_path = fastq_file.split('/')

        # something like: 10528, 10528EJ0019L01, 10528EJpool03_S19_L005_R1_001.fastq.gz
        project, library, filename = split_path[-3:]
        fastq_file_relative = os.path.join(*split_path[-3:])

        # get information from the filename
        re_match = re.match( r'(.*)_(.*)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping %s" % fastq_file)
            continue
        pool = re_match.group(1) # e.g.: 10528EJpool03
        lane = re_match.group(3) # e.g.: L00(5)
        readnumber = re_match.group(4) # e.g.: R(1)

        new_filename = "{prefix}_{lane}_{library}_{readnumber}.fastq.gz".format(**locals())
        new_filename_relative = os.path.join ( os.path.dirname(fastq_file_relative), new_filename )
        new_filename_absolute = os.path.join ( os.path.dirname(fastq_file) , new_filename )

        #Paranoia. Rather than checking if the file exists, create it exclusively.
        #That way, no possible race condition that can cause one file to be renamed over
        #another file.
        with open(new_filename_absolute, 'x') as tmp_fd:
            log( "mv %s %s" % (fastq_file_relative, new_filename_relative) )
            os.replace(fastq_file, new_filename_absolute)

        #Only if we actually renamed a file, note the project as one we've processed.
        proj_seen.append(project)

    # Now deal with the undetermined files.  Have we decided what to do with these?
    # Maybe just leave them alone?
    demux_folder_undetermined_fastq = glob.glob( os.path.join( demux_folder, "Undetermined_*" ) )

    for undet_file_absolute in demux_folder_undetermined_fastq:
        split_path = undet_file_absolute.split('/')
        filename = split_path[-1]

        # eg. Undetermined_S0_L004_R1_001.fastq.gz
        re_match = re.match( r'undetermined_(.*)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping %s" % fastq_file)
            continue

        lane = re_match.group(2)
        readnumber = re_match.group(3)

        # eg. 160811_D00261_0355_BC9DA7ANXX_4_unassigned_1.fastq.gz
        new_filename = "{prefix}_{lane}_unassigned_{readnumber}.fastq.gz".format(**locals())

        new_filename_absolute = os.path.join ( os.path.dirname(undet_file_absolute), new_filename )

        #See comment above
        with open(new_filename_absolute, 'x') as tmp_fd:
            log( "mv %s %s" % (filename, new_filename) )
            os.rename(undet_file_absolute, new_filename_absolute)

    # Finally return the projects processed
    return proj_seen

if __name__ == '__main__':
    main()
