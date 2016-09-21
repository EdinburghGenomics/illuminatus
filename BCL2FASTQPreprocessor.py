#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command line to run BCL2FASTQ.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   ...Apparently it is, as there is no way to get bcl2fastq to demux just
      one lane without making a split samplesheet.
"""
import os

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

    #FIXME - this is wrong, if we need to split the SS.
    def get_bcl2fastq_command(self):
        """Return the full command string for BCL2FASTQ
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

        return ' '.join(cmd)

    # Here's what I'd do if we do need to process and/or split the samplesheet:
    def get_parts(self):
        """Returns a list of SampleSheet suffixes, like:
           [ 'indexLength_6_lanes3_readlen151_index6nn', ...]
        """
        #If we're only splitting by lanes this can just be eg. 'lanes1245'
        return [ 'lanes' + ''.join(self.lanes) ]

    def get_processed_samplesheet(self, ss_name):
        """Returns the content of the specified samplesheet
        """
        #Just now there's only one
        assert [ss_name] == self.get_parts()

        return "PROCESSED"

    def get_partial_bcl2fastq_command(self, ss_name, ss_template="{}.csv"):
        """Returns the content of the specified samplesheet
        """
        #Just now there's only one
        assert [ss_name] == self.get_parts()

        cmd = ['bcl2fastq']

        #Add the abspath for the data folder
        cmd.append("-R '%s'" % self._rundir)
        if self._destdir:
            cmd.append("-o '%s'" % self._destdir)
        cmd.append("--sample-sheet %s" % ss_template.format(ss_name) )
        cmd.append("--fastq-compression-level 6")

        cmd.append("--barcode-mismatches %d" % self.barcode_mismatches )

        #Add base masks per lane
        for lane in self.lanes:
            bm = self._bme.get_base_mask_for_lane(lane)
            cmd.append("--use-bases-mask '%s:%s'" % ( lane, bm ) )

        return ' '.join(cmd)

def main():
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <lane> [<lane> ...]
    """
    pp = BCL2FASTQPreprocessor(sys.argv[1], sys.argv[2:])

    print("#Running bcl2fastq on %d lanes." % len(pp.lanes))

    #Write partial SampleSheet files to ./split_samplesheets
    try:
        os.mkdir(os.path.join(run_dir, 'split_samplesheets'))
    except FileExistsError:
        pass

    ss_template = os.path.join(run_dir, 'split_samplesheets', 'SampleSheet_{}.csv');

    for ss_part in pp.get_parts():

        #print("Writing %s." % ss_template.format(ss_part))

        with open(ss_template.format(ss_part), 'w') as ss_fh:
            print(pp.get_processed_samplesheet(ss_part), file=sf_fh)

        print(pp.get_partial_bcl2fastq_command(ss_part, ss_template))


if __name__ == '__main__':
    main()
