#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command line to run BCL2FASTQ.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
"""
import os, sys, re

from illuminatus.BaseMaskExtractor import BaseMaskExtractor

class BCL2FASTQPreprocessor:

    def __init__(self, run_dir, lanes=None, dest=None):

        #Read data_dir and check that all lanes are in the SampleSheet.
        #Or, can we specify lanes=None to do all lanes?
        #Hmmm.
        self._rundir = run_dir
        self._destdir = dest

        self._samplesheet = os.path.join(self._rundir, "SampleSheet.csv")
        self._runinfo = os.path.join(self._rundir, "RunInfo.xml")

        self._bme = BaseMaskExtractor(self._samplesheet, self._runinfo)

        #Allow lanes to be filled in automatically
        self.lanes = sorted(set( lanes or self._bme.get_lanes() ))
        self.lanes = [ str(l) for l in self.lanes ]

        assert self.lanes

        # FIXME - this should be picked up from a configuration file or embedded
        # in the sample sheet.
        self.barcode_mismatches = 1

    def get_bcl2fastq_command(self):
        """Return the full command string for BCL2FASTQ.  The driver should
           set PATH so that the right version of the software gets run.
        """
        cmd = ['bcl2fastq']

        #Add the abspath for the data folder
        cmd.append("-R '%s'" % self._rundir)
        if self._destdir:
            cmd.append("-o '%s'" % self._destdir)
        cmd.append("--sample-sheet SampleSheet.csv")
        cmd.append("--fastq-compression-level 6")

        cmd.append("--barcode-mismatches %d" % self.barcode_mismatches )

        #Add base masks per lane
        for lane in self.lanes:
            bm = self._bme.get_base_mask_for_lane(lane)
            cmd.append("--use-bases-mask '%s:%s'" % ( lane, bm ) )

        #Add list of lanes to process, which is controlled by --tiles
        # FIXME - add the ability to append a tile number like _1011 for testing.
        # Maybe set this in the same place as 'barcode_mismatches'?
        cmd.append("--tiles=s_[" + ''.join(self.lanes) + "]")# + "_1011")

        return ' '.join(cmd)

def write_script(dest, pp):
    """Writes out the script to a file called sge_demultiplex.sh in the dest directory.
       And makes it executable.
    """
    command = pp.get_bcl2fastq_command()
    sge_script_name = os.path.join ( dest , "sge_demultiplex.sh" )
    #This directory will be made for us by the driver script.
    sge_out_location = os.path.join( dest , "sge_output/" )

    #Using the .format(**locals()) trick is the easiest way to interpolate variables into strings.  Also remove indents
    #with a regex.
    sge_command = re.sub('\n\s+', '\n',
    """#!/bin/bash
       #$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe qc 8 -t 1-1 -q casava
       #$ -N demultiplexing  -o {sge_out_location} -e {sge_out_location}

       echo $PWD
       printenv
       echo -e "\\nSGE_TASK_ID=$SGE_TASK_ID\\n"

       echo "Starting Casava for lane: {pp.lanes}."
       set +x

       PATH="/ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/:$PATH"
       {command}
    """).format(**locals())

    with open( sge_script_name, 'w' ) as f:
        f.write( sge_command )
        make_executable(f)

def make_executable(fh):
    """Code snippet to achieve the equivalent of "chmod +x" on an open FH.
       Copy R bits to X to achieve comod +x
    """
    mode = os.stat(fh.fileno()).st_mode
    os.chmod(fh.fileno(), mode | (mode & 0o444) >> 2)


def main(run_dir, dest, *lanes):
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <dest_dir> [<lane> ...]
    """
    pp = BCL2FASTQPreprocessor(run_dir, dest=dest, lanes=lanes)

    print("#Running bcl2fastq on %d lanes." % len(pp.lanes))

    print("#Command will be: " + pp.get_bcl2fastq_command())

    write_script( dest=dest, pp=pp )

if __name__ == '__main__':
    main(*sys.argv[1:])
