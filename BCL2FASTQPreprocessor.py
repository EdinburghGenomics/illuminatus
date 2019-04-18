#!/usr/bin/env python3

"""This command sets up everything needed to run BCL2FASTQ on a given lane,
   and outputs the appropriate command script (do_demultiplexN.sh) to run
   BCL2FASTQ.
   This in turn is going to be invoked by Snakefile.demux
   It could also edit and/or split the samplesheet, but we're hoping this
   will not be necessary.
   If it is, see commit 5d8aebcd0d for my outline code to do this.
"""
import os, sys
import configparser
from collections import defaultdict
from itertools import dropwhile, takewhile
from subprocess import check_output, DEVNULL

from illuminatus.BaseMaskExtractor import BaseMaskExtractor


class BCL2FASTQPreprocessor:

    def __init__(self, run_dir, lane, dest=None):

        #Read data_dir and check that requested lane is in the SampleSheet.
        self._rundir = run_dir
        self._destdir = dest

        self._samplesheet = os.path.join(self._rundir, "SampleSheet.csv")
        self._runinfo = os.path.join(self._rundir, "RunInfo.xml")

        self._bme = BaseMaskExtractor(self._samplesheet, self._runinfo)

        #Check the lane is valid
        self.lane = str(lane)
        assert self._bme.get_lanes(), \
            "SampleSheet.csv does not seem to list any lanes."
        assert self.lane in [ str(l) for l in self._bme.get_lanes() ], \
            "{!r} not in {!r}".format(lane, self._bme.get_lanes())

        self.ini_settings = defaultdict(dict)

        # Options embedded in the Sample Sheet override the default.
        # pipeline_settings.ini override both.
        for i in [ lambda: self.load_samplesheet_ini(),
                   lambda: self.load_ini_file( os.path.join(self._rundir, "pipeline_settings.ini") ),
                   lambda: self.load_ini_file( os.path.join(self._rundir, "pipeline_settings-lane{}.ini" % self.lane ) ) ]:
            i()

            # Special case for barcode-mismatches, even though we'll normally do this by retry.
            for k in list(self.ini_settings['bcl2fastq'].keys()):
                # Per-lane --barcode-mismatches overrides the default
                if k == '--barcode-mismatches-lane%s' % self.lane:
                    self.ini_settings['bcl2fastq']['--barcode-mismatches'] = \
                        self.ini_settings['bcl2fastq'][k]
                # delete it to avoid further processing
                if k.startswith('--barcode-mismatches-'):
                    del self.ini_settings['bcl2fastq'][k]

    def get_bcl2fastq_commands(self):
        """Return the full command strings for BCL2FASTQ, as a list of lists.  The caller should
           have set PATH so that the right version of the software gets picked up.
        """
        lane = self.lane
        # If the command isn't found this is an immediate error.
        bcl2fastq = check_output("which bcl2fastq".split(), stderr=DEVNULL, universal_newlines=True).rstrip()

        # If the result is a symlink, resolve it
        bcl2fastq = os.path.realpath(bcl2fastq)

        cmds = [ ["LANE=%s" % lane] ]

        # Print out the version each time the script is run
        if self._destdir:
            cmds.append([bcl2fastq, '--version', '2>', "'%s'/lane${LANE}/bcl2fastq.version" % self._destdir])

        # Build the main bcl2fastq command
        cmd = [bcl2fastq]

        # Add the abspath for the data folder
        cmd.append("-R '%s'" % self._rundir)
        if self._destdir:
            cmd.append("-o '%s'/lane${LANE}" % self._destdir)
        cmd.append("--fastq-compression-level 6")

        # Add base mask for this lane
        bm = self._bme.get_base_mask_for_lane(lane)
        cmd.append("--use-bases-mask '%s:%s'" % ( lane, bm ) )

        # Specify the lane to process, which is controlled by --tiles
        # Slimmed-down runs override this setting but will still include $LANE to pick up the lane number
        cmd.append("--tiles=s_[$LANE]")

        # And we actually need to strip the other lanes out of the SampleSheet.csv, due to the bug that bcl2fastq
        # will do an index collision check for ALL lanes even if you are only trying to process one,
        # which breaks the per-lane-base-mask feature.
        # We can do this munging on the fly (assuming we never see more than 8 lanes)...
        cmd.append('''--sample-sheet <(grep -v "`tr -d $LANE <<<'^[12345678],'`" '%s')''' %
                        os.path.join( self._rundir, "SampleSheet.csv" ) )

        # Number of threads to use should be set by the caller (ie. Snakemake)
        cmd.append("-p ${PROCESSING_THREADS:-10}")

        # now that the cmd array is complete will evaluate the pipeline_settings.ini file
        # every setting must be either replaced or appended to the cmd array
        # this won't work with options that appear multiple times like --use-base-mask (don't think we need this though)
        barcode_mismatches_set = None
        for ini_option, val in self.ini_settings['bcl2fastq'].items(): # section in the ini file is bcl2fastq
            ## special case for option --tiles
            delimiter = "=" if ini_option in ["--tiles"] else " "

            if ini_option == '--barcode-mismatches':
                barcode_mismatches_set = val

            replace_index = [ i for i, c in enumerate(cmd)
                              if c.split(delimiter)[0] == ini_option ]
            replace_value = '{}{}{}'.format( ini_option,
                                             delimiter,
                                             val )
            if replace_index:
                #print ("replacing from pipeline_settings.ini option "+ ini_option)
                cmd[replace_index[0]] = replace_value
            else: ## so must be appended
                #print ("appending from pipeline_settings.ini " + ini_option)
                cmd.append(replace_value)


        if self._destdir:
            logfile = "'%s'/lane${LANE}/bcl2fastq.log" % self._destdir
            optsfile = "'%s'/lane${LANE}/bcl2fastq.opts" % self._destdir

            # In this, the normal case, we try barcode-mismatches set to 1 and then to 0.
            # So here we have a Python script writing a shell script. See doc/mismatches_flag_v2.txt
            # for an explanation. Proabably if I wrote this again I'd just have a wrapper script, or
            # at least a template.
            if barcode_mismatches_set is None:
                barcode_mismatches = '--barcode-mismatches 1'
                old_logfile = "'%s'/lane${LANE}/bcl2fastq_mismatch1.log" % self._destdir

                m1_cmd = cmd + [ barcode_mismatches, "2>%s" % logfile ]
                m1_cmd.extend(['&& echo', barcode_mismatches, '>', optsfile])

                cmds.append(["if ! ( "] + m1_cmd + [") ; then"])

                cmds.append(["if grep -qF 'Barcode collision for barcodes:'", logfile, "; then"])
                # If the log says there was a collision, retry with mismatch 0

                barcode_mismatches = '--barcode-mismatches 0'
                cmds.append(["  mv", logfile, old_logfile])
                m0_cmd = ["  "] + cmd + [ barcode_mismatches, "2>%s" % logfile ]
                m0_cmd.extend(['&& echo', barcode_mismatches, '>', optsfile])
                cmds.append(m0_cmd)

                # If the log didn't mention a collision, just fail.
                # Also close the if statements.
                cmds.extend([ ["else"], ["  false"], ["fi"], ["fi"] ])

            else:
                # Simpler case - barcode-mismatches was set explicitly
                cmds.append( cmd + [ "2>%s" % logfile, '&& echo', "--barcode-mismatches '%s'" % barcode_mismatches_set, '>', optsfile ] )

            ''' Here's a hack that ensures we get empty FASTQ files for missing samples (but not missing
                unassigned, apparently)
                Actually we may not need this, if the samples still show up in Stats.json and therefore
                in the reports???
                It seems they do (see run 171115_M01145_0050_000000000-BHCPV) so I've disabled this. The
                empty files upset FastQC and probably other things too.
            '''

            # cmds.append(['#Hack to force creation of empty files'])
            # cmds.append([
            #      (r'''sed -ne '/INFO: Created FASTQ file /s/.*"\(.*\)"/\1/p' '%s'/lane${LANE}/bcl2fastq.log''' % self._destdir),
            #      (r''' | ( while read -r l; do [ -e "$l" ] || true | gzip -c > "$l" ; done )''') ])

        else:
            # self._destdir is not set
            # Even simpler case, no barcode-mismatches setting or log redirection
            cmds.append( cmd )

        return cmds

    def load_samplesheet_ini(self):
        """Loads the [bcl2fastq] section from self._samplesheet into self.ini_settings,
           allowing things like --barcode-mismatches to be embedded in the SampleSheet.csv
        """
        cp = configparser.ConfigParser(empty_lines_in_values=False)
        try:
            with open(self._samplesheet) as sfh:
                cp.read_file( takewhile(lambda x: not x.startswith('[Data]'),
                                        dropwhile(lambda x: not x.startswith('[bcl2fastq]'), sfh)),
                              self._samplesheet )

                for section in cp.sections():
                    # Cast all to strings
                    self.ini_settings[section].update(cp.items(section))

        except Exception:
            return

    def load_ini_file(self, ini_file):
        """ Read the options from config_file into self.ini_settings,
            overwriting anything already there.
        """
        cp = configparser.ConfigParser(empty_lines_in_values=False)
        try:
            cp.read(ini_file)
            for section in cp.sections():
                #conf_items = { k: str(v) for k, v in cp.items(section) }
                self.ini_settings[section].update(cp.items(section))

        except Exception:
            raise

def main(run_dir, dest, lane):
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <dest_dir> <lane>
    """
    run_dir = os.path.abspath(run_dir)
    pp = BCL2FASTQPreprocessor(run_dir, dest=dest, lane=lane)

    script_name = os.path.join( dest , "do_demultiplex%s.sh" % lane )

    lines = [ "#Run bcl2fastq on lane %s." % lane ] + \
            [ ' '.join(c) for c in pp.get_bcl2fastq_commands() ]

    print("\n>>> Script being written...\ncat >%s <<END" % script_name)
    with open( script_name, 'w' ) as fh:
        for l in lines:
            print(l)
            print(l, file=fh)
    print("END\n")

if __name__ == '__main__':
    main(*sys.argv[1:])
