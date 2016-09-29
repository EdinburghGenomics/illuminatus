#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given run,
   and outputs the appropriate command line to run BCL2FASTQ.
   It may also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
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
        cmd.append("--tiles=s_[" + ''.join(self.lanes) + "]")

        return ' '.join(cmd)

def main():
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <lane> [<lane> ...]
    """
    pp = BCL2FASTQPreprocessor(sys.argv[1], sys.argv[2:])

    print("#Running bcl2fastq on %d lanes." % len(pp.lanes))

    if pp.get_parts():
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

    else:
        print(pp.get_bcl2fastq_command())

if __name__ == '__main__':
    main()
