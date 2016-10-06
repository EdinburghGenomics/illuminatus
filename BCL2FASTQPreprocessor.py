#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command line to run BCL2FASTQ.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
"""
import os, sys

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

        #FIXME = self._bme.get_lanes() seems to be broken, according to the
        #test test_hiseq_all_lanes
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
        cmd.append("--tiles=s_[" + ''.join(self.lanes) + "]")# + "_1011") #FIXME/DEBUG - need to remove _1011

        return ' '.join(cmd)

class SGE_script_writer:
    """ this will write the generated demultiplexing command as a SGE submit script to <dest>/demultiplexing/demultiplex.sh
        with the new cluster this won't be needed
    """
    def __init__(self, dest, command):
        self.demux_destination = dest 
        self.command = command
        self.sge_script_name = os.path.join ( self.demux_destination , "sge_demultiplex.sh" )

    def _prepare_sge_command( self, command ):
        sge_out_location = os.path.join( self.demux_destination , "sge_output/" )
        sge_commands = [
        """#!/bin/bash""",
        "#$ -cwd -v PATH -v LD_LIBRARY_PATH -sync yes -pe qc 8 -t 1-1 -q casava -N demultiplexing  -o " + sge_out_location + " -e " + sge_out_location,
        """
        echo $PWD
        printenv""",
        """
        echo -e "\nSGE_TASK_ID=$SGE_TASK_ID\n"

        if [ "$SGE_TASK_ID" -eq "1" ]; then
            echo "Starting Casava for lane: 12345678 samplesheet: SampleSheet_in_HiSeq_format_forCasava2_17.csv  unalignedDirectoryName: Unaligned_SampleSheet_in_HiSeq_format_lanes12345678_readlen151_index6nn";
        """,
        "/ifs/software/linux_x86_64/Illumina_pipeline/bcl2fastq2-v2.17.1.14-bin/bin/"+command,
        """
        fi
        """
        ]

        return "\n".join(sge_commands)

    def write(self):
        sge_command = self._prepare_sge_command( self.command )

        f = open( self.sge_script_name, 'w' )
        f.write( sge_command )
        f.close()

def main():
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <dest_dir> [<lane> ...]
    """
    pp = BCL2FASTQPreprocessor(run_dir=sys.argv[1], dest=sys.argv[2], lanes=sys.argv[3:])

    print("#Running bcl2fastq on %d lanes." % len(pp.lanes))

    print(pp.get_bcl2fastq_command())

    sge_script = SGE_script_writer( dest = sys.argv[2] , command = pp.get_bcl2fastq_command() )
    sge_script.write()

if __name__ == '__main__':
    main()
