#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command line to run BCL2FASTQ.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
"""
import os, sys, re, csv

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
        # FIXME - add the ability to append a tile number like _1011 for testing.
        # Maybe set this in the same place as 'barcode_mismatches'?
        cmd.append("--tiles=s_[" + ''.join(self.lanes) + "]")# + "_1011")

        ## now that the cmd array is complete will evaluate the settings.ini file
        ## every setting must be either replaced or appended to the cmd array
        ## this won't work with options that appear multiple times like --use-base-mask (don't think we need this though)
        for ini_option in self.ini_settings.get_all_options('bcl2fastq'): # section in the ini file is bcl2fastq
            replaced = False
            for option in cmd:
                if ini_option in option:
                    #print ("option "+ ini_option +" must be replaced")
                    if ini_option == "--tiles": ## special case for option --tile
                        delimiter="="
                    else:
                        delimiter=" "
                    cmd[cmd.index(option)] = ini_option + delimiter + self.ini_settings.get_value( 'bcl2fastq', ini_option) 
                    replaced = True
            if not replaced: ## so must be appended
                #print ("option " + ini_option + " must be appended")
                cmd.append("%s %s" % (ini_option, self.ini_settings.get_value( 'bcl2fastq', ini_option)) )
                

        return ' '.join(cmd)

def main(run_dir, dest, *lanes):
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <dest_dir> [<lane> ...]
    """
    pp = BCL2FASTQPreprocessor(run_dir, dest=dest, lanes=lanes)

    script_name = os.path.join( dest , "do_demultiplex.sh" )

    lines = [
        "#Running bcl2fastq on %d lanes." % len(pp.lanes),
        pp.get_bcl2fastq_command()
    ]

    with open( script_name, 'w' ) as fh:
        for l in lines:
            print(l)
            print(l, file=fh)

if __name__ == '__main__':
    main(*sys.argv[1:])
