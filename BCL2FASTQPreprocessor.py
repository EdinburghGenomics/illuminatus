#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command line to run BCL2FASTQ.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
"""
import os, sys, re, csv

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
        # RE: using a configuration file for now (settings.txt)
        settings_hash = self._parse_settingsFile()

        # if bcl2fastq parameter names were ever to change (like they have in the past) we will need to adapt it in several places.
        # Namely this function and in get_bcl2fastq_command()
        if "--barcode-mismatches" in settings_hash:
            self.barcode_mismatches = int( settings_hash[ "--barcode-mismatches" ] ) # I assume the error checking was handled during parsing, so here data is reliable.
        else:
            self.barcode_mismatches = 1

    def _parse_settingsFile(self):
        """ Not discussed the format of the file, yet.
            For now will assume 1 bcl2fastq command per line. Parameter and value separated by space. Location: run_folder/settings.txt
            e.g.:
            --barcode-mismatches 1
            --fastq-compression-level 6
        """
        ### TODO: needs exception handling
        settingsFile = os.path.join( self._rundir , "settings.txt" )

        if not os.path.exists( settingsFile ):
            return None

        # will fill up this hash:
        demux_settings = {}
        # e.g. demux_settings = { "--barcode-mismatches" : "1" , "--fastq-compression-level" : "6" }

        # should probably use csvreader if format becomes more sophisticated
        with open(settingsFile) as f:
            for line in f:
                settingsData = line.split(" ")
                if len(settingsData) == 2: # settingsData: [ "--barcode-mismatches" , "1" ]
                    demux_settings[ settingsData[0] ] = int( settingsData[1].rstrip("\n") )
        return demux_settings

    def get_bcl2fastq_command(self):
        """Return the full command string for BCL2FASTQ.  The driver should
           set PATH so that the right version of the software gets run.
        """
        cmd = ['bcl2fastq']


        #Add the abspath for the data folder
        cmd.append("-R '%s'" % self._rundir)
        if self._destdir:
            cmd.append("-o '%s'" % self._destdir)
        #cmd.append("--sample-sheet SampleSheet.csv") # this samplesheet needs to either be copied or
        cmd.append("--sample-sheet '%s'" % os.path.join( self._rundir , "SampleSheet.csv" ) )
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
