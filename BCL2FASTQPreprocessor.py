#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command script (do_demultiplex.sh) to run
   BCL2FASTQ.
   This in turn is going to be invoked by BCL2FASTQRunner.sh.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
"""
import os, sys, re

from illuminatus.BaseMaskExtractor import BaseMaskExtractor
from illuminatus.ConfigFileReader import ConfigFileReader


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
        # RE: using a configuration file (settings.ini)
        ini_file = os.path.join( self._rundir , "settings.ini" )
        self.ini_settings = ConfigFileReader( ini_file )

        # Can be overriden by caller. Are we ever actully doing this?
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
        cmd.append("--sample-sheet '%s'" % os.path.join( self._rundir , "SampleSheet.csv" ) )
        cmd.append("--fastq-compression-level 6")
        cmd.append("--barcode-mismatches %d" % self.barcode_mismatches )

        #Add base masks per lane
        for lane in self.lanes:
            bm = self._bme.get_base_mask_for_lane(lane)
            cmd.append("--use-bases-mask '%s:%s'" % ( lane, bm ) )

        # Add list of lanes to process, which is controlled by --tiles
        cmd.append("--tiles=s_[" + ''.join(self.lanes) + "]")

        ## now that the cmd array is complete will evaluate the settings.ini file
        ## every setting must be either replaced or appended to the cmd array
        ## this won't work with options that appear multiple times like --use-base-mask (don't think we need this though)
        for ini_option in self.ini_settings.get_all_options('bcl2fastq'): # section in the ini file is bcl2fastq
            ## special case for option --tiles
            delimiter = "=" if ini_option == "--tiles" else " "

            replace_index = [ i for i, c in enumerate(cmd)
                              if re.split(r'[\s=]', c)[0] == ini_option ]
            replace_value = ( ini_option + delimiter +
                              self.ini_settings.get_value('bcl2fastq', ini_option).format(lanes=''.join(self.lanes)) )
            if replace_index:
                #print ("replacing from settings.ini option "+ ini_option)
                cmd[replace_index[0]] = replace_value
            else: ## so must be appended
                #print ("appending from settings.ini " + ini_option)
                cmd.append(replace_value)

        return ' '.join(cmd)

def main(run_dir, dest, *lanes):
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <dest_dir> [<lane> ...]
    """
    run_dir = os.path.abspath(run_dir)
    pp = BCL2FASTQPreprocessor(run_dir, dest=dest, lanes=lanes)

    script_name = os.path.join( dest , "do_demultiplex.sh" )

    lines = [
        "#Run bcl2fastq on %d lanes." % len(pp.lanes),
        pp.get_bcl2fastq_command()
    ]

    print("\n>>> Script being written to %s..." % script_name)
    with open( script_name, 'w' ) as fh:
        for l in lines:
            print(l)
            print(l, file=fh)
    print("<<< End of script\n")

if __name__ == '__main__':
    main(*sys.argv[1:])
