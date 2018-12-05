#!/usr/bin/env python3

""" "Fixes" the output of bcl2fastq to meet our requirements.
    Files are renamed, grouped by pool, and shifted out of the demultiplexing directory.
    projects_ready.txt is added listing the projects found
    projects_pending.txt is deleted if it exists
"""
# I guess we could go back to keeping the files in /ifs/runqc until they are renamed,
# and this might be sensible for backup purposes. In any case I could do this with a
# symlink so the code can stay the same.

import os, sys, re, time
from glob import glob
from yaml_ordered import yaml

# Global error collector
ERRORS = set()

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

        project_seen = do_renames(output_dir, prefix, log=log)

        if ERRORS:
            log("# There were errors...")
            for e in ERRORS:
                print("Error: %s" % e)
                log("# %s" % e)
        else:
            save_projects_ready(output_dir, project_seen)
            log("# DONE. And projects_ready.txt was saved out.")


def save_projects_ready(output_dir, proj_seen):
    """Save out what we've processed. There might be stuff already in projects_ready.txt
       and we want to maintain the contents as a sorted set (as per 'sort -u')
    """
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

def check_project_name(proj_name):
    """ BCL2FASTQ is already quite fussy about project names.
        This will just chack that the project name isn't going to clobber any
        of our folders.
    """
    if "." in proj_name:
        raise ValueError("Invalid project name {!r} contains a period.".format(proj_name))

    if proj_name in "counts demultiplexing md5sums multiqc_reports QC seqdata slurm_output".split():
        raise ValueError("Invalid project name {!r} conflicts with reserved names.".format(proj_name))

def do_renames(output_dir, runid, log = lambda m: print(m)):
    """ The main part of the code that does the renaming (moving).
        Primary reason for splitting this out from main() is to separate
        the sys.argv processing and the log file handling in order to
        simplify unit testing.
        Returns the list of projects for which files have been renamed.
    """
    proj_seen = set()
    def add_project(proj_name):
        check_project_name(proj_name)
        proj_seen.add(proj_name)

    # Previously we scanned for *.fastq.gz files, but it's more sensible to look for an explicit
    # list of projects. The projects don't get listed in Stats.json, so go back to sample_summary.yml
    # directly. This allows us to proceed even when no files were produced (ie. all the barcodes are wrong)
    try:
        with open( os.path.join( output_dir, "seqdata/pipeline" , "sample_summary.yml" ) ) as sfh:
            summary = yaml.safe_load(sfh)
            for proj in summary['ProjectInfo']:
                add_project(proj)

        # Now we can't add any new projects.
        def add_project(proj_name):
            assert proj_name in proj_seen
    except FileNotFoundError:
        log("Failed to read seqdata/pipeline/sample_summary.yml. Proceeding anyway.")

    # Notwithstanding the list of projects obtained by the summary, look for fastq.gz files in all
    # locations.
    # Either we have a list of projects and will find corresponding fastq, or else we have no list and
    # will make it up as we go along.
    for fastq_file in glob(os.path.join( output_dir, "demultiplexing/lane*" , "*/*/*.fastq.gz" )):

        #os.path.split is unhelpful here. Just do it the obvious way.
        # something like: 10528, 10528EJ0019L01, 10528EJpool03_S19_L005_R1_001.fastq.gz
        lane_dir, project, pool_and_library, filename = fastq_file.split('/')[-4:]

        #Note the project as one we've processed.
        add_project(project)

        # get information from the filename
        re_match = re.match( r'(.*)_(S[0-9]+)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping (regex mismatch) %s" % fastq_file)
            continue
        samplename = re_match.group(1) # e.g.: We ignore this!
        lane = re_match.group(3) # e.g.: L00(5)
        readnumber = re_match.group(4) # e.g.: R(1)

        # Check lane matches the directory name
        if not lane_dir == 'lane{}'.format(lane):
            log("# skipping (lane mismatch) %s" % fastq_file)
            continue

        # split out library and pool
        try:
            pool, library = pool_and_library.split('__')
        except ValueError:
            #log("# skipping (no pool__library) %s" % fastq_file)
            #continue
            # Decided be a little less strict here. This is also needed for PhiX
            pool = 'NoPool'
            library = pool_and_library

        new_filename = "{runid}_{lane}_{library}_{readnumber}.fastq.gz".format(**locals())
        new_filename_relative = os.path.join ( project, pool, new_filename )
        new_filename_absolute = os.path.join ( output_dir, project, pool, new_filename )

        #Make the directory to put it in
        os.makedirs(os.path.dirname(new_filename_absolute), exist_ok=True)

        #Paranoia. Rather than checking if the file exists, create it exclusively.
        #That way, no possible race condition that can cause one file to be renamed over
        #another file (ignoring remote NFS race conditions).
        try:
            log( "mv %s %s" % ('/'.join(fastq_file.split('/')[-4:]), new_filename_relative) )

            with open(new_filename_absolute, 'x') as tmp_fd:
                os.replace(fastq_file, new_filename_absolute)
        except FileExistsError:
            log("# FileExistsError renaming %s" % new_filename_relative)
            raise

    # Now go again for files not in a subdirectory (if Sample_Name was blank)
    # (apologies for the copy-paste)
    for fastq_file in glob(os.path.join( output_dir, "demultiplexing/lane*" , "*/*.fastq.gz" )):

        #os.path.split is unhelpful here. Just do it the obvious way.
        # something like: 10528, 10528EJ0019L01, 10528EJpool03_S19_L005_R1_001.fastq.gz
        lane_dir, project, filename = fastq_file.split('/')[-3:]

        #Note the project as one we've processed.
        add_project(project)

        # get information from the filename
        # Note this ignores index reads.
        re_match = re.match( r'(.*)_(S[0-9]+)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping (regex mismatch) %s" % fastq_file)
            continue
        pool_and_library = re_match.group(1) # e.g.: 10528EJpool03__10528EJ0019L01
        lane = re_match.group(3) # e.g.: L00(5)
        readnumber = re_match.group(4) # e.g.: R(1)

        # Check lane matches the directory name
        if not lane_dir == 'lane{}'.format(lane):
            log("# skipping (lane mismatch) %s" % fastq_file)
            continue

        # split out library and pool
        try:
            pool, library = pool_and_library.split('__')
        except ValueError:
            #log("# skipping (no pool__library) %s" % fastq_file)
            #continue
            # Decided be a little less strict here. This is also needed for PhiX
            pool = 'NoPool'
            library = pool_and_library

        new_filename = "{runid}_{lane}_{library}_{readnumber}.fastq.gz".format(**locals())
        new_filename_relative = os.path.join ( project, pool, new_filename )
        new_filename_absolute = os.path.join ( output_dir, project, pool, new_filename )

        #Make the directory to put it in
        os.makedirs(os.path.dirname(new_filename_absolute), exist_ok=True)

        #Paranoia? Rather than checking if the file exists, create it exclusively.
        #That way, no possible race condition that can cause one file to be renamed over
        #another file.
        try:
            log( "mv %s %s" % ('/'.join(fastq_file.split('/')[-3:]), new_filename_relative) )

            with open(new_filename_absolute, 'x') as tmp_fd:
                os.replace(fastq_file, new_filename_absolute)
        except FileExistsError:
            log("# FileExistsError renaming %s" % new_filename_relative)
            raise

    # Now deal with the undetermined files.
    for undet_file_absolute in glob(os.path.join( output_dir, "demultiplexing/lane*", "[Uu]ndetermined_*" )):
        lane_dir, filename = undet_file_absolute.split('/')[-2:]

        # eg. Undetermined_S0_L004_R1_001.fastq.gz
        re_match = re.match( r'undetermined_(.*)_L00(\d)_R(\d)_\d+.fastq.gz', filename, re.I)

        if not re_match:
            log("# skipping %s" % fastq_file)
            continue

        lane = re_match.group(2)
        readnumber = re_match.group(3)

        # Check lane matches the directory name
        if not lane_dir == 'lane{}'.format(lane):
            log("# skipping (lane mismatch) %s" % fastq_file)
            continue

        # eg. 160811_D00261_0355_BC9DA7ANXX_4_unassigned_1.fastq.gz
        new_filename = "{runid}_{lane}_unassigned_{readnumber}.fastq.gz".format(**locals())

        new_filename_absolute = os.path.join ( output_dir, new_filename )

        #See comment above
        try:
            log( "mv %s %s" % ( os.path.join("demultiplexing", filename), new_filename) )

            with open(new_filename_absolute, 'x') as tmp_fd:
                os.rename(undet_file_absolute, new_filename_absolute)
        except FileExistsError:
            log("# FileExistsError renaming %s" % new_filename)
            raise

    # Cleanup empty project directories (as per Cleanup.py) then warn if any dirs
    # remain (or, if fact, that's an error).
    for lane_dir in glob(os.path.join(output_dir, "demultiplexing", "lane*")):
        for proj in list(proj_seen):
            for root, dirs, files in os.walk(
                                         os.path.join(lane_dir, proj),
                                         topdown=False ):
                try:
                    os.rmdir(root)
                    log("rmdir '%s'" % root)
                except Exception:
                    # Assume it was non-empty.
                    ERRORS.add("Failed to remove all project directories from demultiplexing area.")
                    log("# could not remove dir '%s'" % root)
                    # And we cannot say the project is ready.
                    # TODO - Should I add it to pending??
                    proj_seen.discard(proj)

    # Finally return the projects processed
    return proj_seen

if __name__ == '__main__':
    print("Running: " + ' '.join(sys.argv))
    main(*sys.argv[1:])
    if ERRORS: exit(1)
