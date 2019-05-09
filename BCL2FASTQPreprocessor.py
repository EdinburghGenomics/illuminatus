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

import pystache
from shlex import quote as shell_quote

from illuminatus.BaseMaskExtractor import BaseMaskExtractor
from illuminatus.RunInfoXMLParser import RunInfoXMLParser

# Capture this before any possible change of directory.
SCRIPTDIR = os.path.dirname(os.path.abspath(__file__))

class BCL2FASTQPreprocessor:

    def __init__(self, run_dir, lane, dest=None):

        #Read data_dir and check that requested lane is in the SampleSheet.
        self._rundir = run_dir
        self._destdir = dest

        self._samplesheet = os.path.join(self._rundir, "SampleSheet.csv")
        self._runinfo = os.path.join(self._rundir, "RunInfo.xml")

        self._bme = BaseMaskExtractor(self._samplesheet, self._runinfo)

        # Get the run name from the RunInfo.xml
        self._runinfo = RunInfoXMLParser( self._rundir ).run_info

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
                   lambda: self.load_ini_file(
                        os.path.join(self._rundir, "pipeline_settings-lane{}.ini".format(self.lane)) ) ]:
            i()

            # Special case for barcode-mismatches, even though we'll normally do this by retry.
            for k in list(self.ini_settings['bcl2fastq'].keys()):
                # Per-lane --barcode-mismatches overrides the default
                if k == '--barcode-mismatches-lane{}'.format(self.lane):
                    self.ini_settings['bcl2fastq']['--barcode-mismatches'] = \
                        self.ini_settings['bcl2fastq'][k]
                # delete it to avoid further processing
                if k.startswith('--barcode-mismatches-'):
                    del self.ini_settings['bcl2fastq'][k]

    def get_bcl2fastq_commands(self):
        """Returns a dict used to populate the template that will produce the script to be run.
           The caller should have set PATH so that the right version of the software gets picked up and
           baked into the file.
        """
        #{'runid': 'bar', 'lane': '3', 'bcl2fastq': '/path/tp/bcl2fastq',
        # 'rundir': 'rundir', 'samplesheet': 'samplesheet' , 'destdir': 'destdir',
        # 'barcode_mismatches' : None , 'bcl2fastq_opts' : ['--foo']}
        res = dict( lane = self.lane,
                    rundir = self._rundir,
                    runid = self._runinfo['RunId'],
                    samplesheet = self._rundir + '/SampleSheet.csv',
                    destdir = self._destdir,
                    barcode_mismatches = None,
                    bcl2fastq_opts = [] )

        # If the command isn't found this is an immediate error.
        res['bcl2fastq'] = os.path.realpath(
                            check_output( "which bcl2fastq".split(),
                                            stderr = DEVNULL,
                                            universal_newlines=True ).rstrip() )

        # Work out all the options plus --barcode-mismatches which is special.
        cmd = res['bcl2fastq_opts']
        cmd.append("--fastq-compression-level 6")

        # Add base mask for this lane
        bm = self._bme.get_base_mask_for_lane(self.lane)
        cmd.append("--use-bases-mask '{}:{}'".format( self.lane, bm ) )

        # Specify the lane to process, which is controlled by --tiles
        # Slimmed-down runs override this setting but will still include $LANE to pick up the lane number
        cmd.append("--tiles=s_[$LANE]")

        # now that the cmd array is complete will evaluate the pipeline_settings.ini file
        # every setting must be either replaced or appended to the cmd array
        # this won't work with options that appear multiple times like --use-base-mask (don't think we need this though)
        for ini_option, val in self.ini_settings['bcl2fastq'].items(): # section in the ini file is bcl2fastq
            ## special case for option --tiles

            if ini_option == '--barcode-mismatches':
                res['barcode_mismatches'] = val

            delimiter = "=" if ini_option in ["--tiles"] else " "
            replace_index = [ i for i, c in enumerate(cmd)
                              if c.split(delimiter)[0] == ini_option ]
            replace_value = '{}{}{}'.format( ini_option, delimiter, val )

            if replace_index:
                #print ("replacing from pipeline_settings.ini option "+ ini_option)
                cmd[replace_index[0]] = replace_value
            else: ## so must be appended
                #print ("appending from pipeline_settings.ini " + ini_option)
                cmd.append(replace_value)

        return res

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

def format_template(adict):
    """Load the Pystache template from tfile and render it with the values in adict,
       applying shell quote escaping by default.
    """
    template_file = os.environ.get("BCL2FASTQ_TEMPLATE",
                                   SCRIPTDIR + '/templates/do_demultiplex.sh.ms')

    myrenderer = pystache.Renderer( escape = shell_quote,
                                    search_dirs = None,
                                    missing_tags = pystache.common.MissingTags.strict )
    with open(template_file) as fh:
        mytemplate = pystache.parse(fh.read())

    return myrenderer.render(mytemplate, adict)

def main(run_dir, dest, lane):
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <dest_dir> <lane>
    """
    run_dir = os.path.abspath(run_dir)
    pp = BCL2FASTQPreprocessor(run_dir, dest=dest, lane=lane)

    script_name = os.path.join( dest , "do_demultiplex{}.sh".format(lane) )

    script = format_template( pp.get_bcl2fastq_commands() )

    print("\n>>> Script being written...\ncat >{} <<END".format(script_name))
    with open( script_name, 'w' ) as fh:
        print(script, end='')
        print(script, file=fh, end='')
    os.chmod(script_name, 0o775)
    print("END\n")

if __name__ == '__main__':
    main(*sys.argv[1:])
