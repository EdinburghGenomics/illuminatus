#!/usr/bin/env python3

"""This command outputs a Sample Sheet suitable for use with do_demultiplex.sh, ie:
    Contains only one lane
    Contains a [bcl2fastq] section with all options
    Has optional revcomp of index2 (or 1)
"""
import os, sys
import configparser
from collections import defaultdict
from itertools import dropwhile, takewhile
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from illuminatus.BaseMaskExtractor import BaseMaskExtractor
from illuminatus.RunInfoXMLParser import RunInfoXMLParser
from illuminatus.RunParametersXMLParser import RunParametersXMLParser

class BCL2FASTQPreprocessor:
    """The name is a hangover from the old script name.
    """
    def __init__(self, run_dir, lane, revcomp):

        #Read data_dir and check that requested lane is in the SampleSheet.
        self.run_dir = run_dir

        self.samplesheet = os.path.join(self.run_dir, "SampleSheet.csv")
        self.runinfo_file = os.path.join(self.run_dir, "RunInfo.xml")

        # This code is a little crufty but is tested and working.
        self.bme = BaseMaskExtractor(self.samplesheet, self.runinfo_file)

        # Get the run name from the RunInfo.xml
        self.run_info = RunInfoXMLParser( self.run_dir ).run_info

        # Check the lane is valid. Note lane must be a str
        assert self.bme.get_lanes(), \
            "SampleSheet.csv does not seem to list any lanes."
        assert str(lane) == lane, \
            "{!r} is not a string".format(lane)
        assert lane  in [ str(l) for l in self.bme.get_lanes() ], \
            "{!r} not in {!r}".format(lane, self.bme.get_lanes())
        self.lane = lane

        # This sets up self.ini_settings()
        self.get_ini_settings()

        # See if we want to revcomp at all
        if revcomp == 'auto':
            self.revcomp = self.infer_revcomp()
        else:
            # Convert None to ''
            self.revcomp = revcomp or ''

    def get_ini_settings(self):
        """Extract the appropriate settings for embedding to the [bcl2fastq] section.
           Sets self.ini_settings
        """
        self.ini_settings = defaultdict(dict)

        # Options embedded in the Sample Sheet override the default.
        # pipeline_settings.ini override both.
        for i in [ lambda: self.load_samplesheet_ini(),
                   lambda: self.load_ini_file( os.path.join(self.run_dir, "pipeline_settings.ini") ),
                   lambda: self.load_ini_file(
                        os.path.join(self.run_dir, "pipeline_settings-lane{}.ini".format(self.lane)) ) ]:
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

    def get_bcl2fastq_options(self):
        """Get the options which will go into the [bcl2fastq] section on the sample sheet.
           Unlike get_ini_settings() this does not set a variable on the object but just returns
           a list.
        """
        bcl2fastq_opts = ["--fastq-compression-level 6"]

        # Add base mask for this lane
        bm = self.bme.get_base_mask_for_lane(self.lane)
        bcl2fastq_opts.append("--use-bases-mask '{}:{}'".format( self.lane, bm ) )

        # Specify the lane to process, which is controlled by --tiles
        # Note that $LANE is going to be interpreted by the shell when the command is run.
        # Slimmed-down runs override this setting but will still include $LANE to pick up the lane number
        bcl2fastq_opts.append("--tiles=s_[$LANE]")

        # now that the bcl2fastq_opts array is complete, evaluate the pipeline_settings.ini file
        # every setting must be either replaced or appended to the bcl2fastq_opts array
        # this won't work with options that appear multiple times like --use-base-mask (don't think we need this though)
        for ini_option, val in self.ini_settings['bcl2fastq'].items(): # section in the ini file is bcl2fastq
            ## special case for option --tiles
            delimiter = "=" if ini_option in ["--tiles"] else " "
            replace_index = [ i for i, c in enumerate(bcl2fastq_opts)
                              if c.split(delimiter)[0] == ini_option ]
            replace_value = '{}{}{}'.format( ini_option, delimiter, val )

            if replace_index:
                #print ("replacing from pipeline_settings.ini option "+ ini_option)
                bcl2fastq_opts[replace_index[0]] = replace_value
            else: ## so must be appended
                #print ("appending from pipeline_settings.ini " + ini_option)
                bcl2fastq_opts.append(replace_value)

        return bcl2fastq_opts

    def infer_revcomp(self):
        """Do we need to do the thing? This is a special hack for certain NovaSeq runs.
        """
        if self.run_info['RunId'].split('_')[1][0] != 'A':
            # Not a NovaSeq run then
            return ''

        rp = RunParametersXMLParser( self.run_dir ).run_parameters
        if rp.get('Consumable Version') == '3':
            # For these we want to revcomp the i5 barcode.
            return '2'

        # In all other cases, nowt to do.
        return ''


    def get_output(self, me):
        """Return a new partial sample sheet as a list of lines.
        """
        res = ['[Header]']

        # Calculate the bcl2fastq_opts:
        # work out all the options plus --barcode-mismatches which is special.
        bcl2fastq_opts = self.get_bcl2fastq_options()

        # OK now we can go through the input sample sheet.
        with open(self.run_dir + '/SampleSheet.csv') as ssfh:
            # We expect a [Header] section.
            assert next(ssfh).strip() == '[Header]'
            for l in ssfh:
                l = l.strip()
                if l == '' or l.startswith('['):
                    break
                if not any(l.startswith(x) for x in ('Description', '#')):
                    res.append(l)
            res.append("Run ID,{}".format(self.run_info['RunId']))
            res.append("Description,Fragment processed with {}".format(me))
            res.append("#Lane,{}".format(self.lane))
            res.append("#Revcomp,{}".format(self.revcomp or 'None'))

            # Now add the bcl2fastq_opts
            res.append('')
            res.append('[bcl2fastq]')
            res.extend(bcl2fastq_opts)
            res.append('')

            # Get to the [Data] line
            for l in ssfh:
                if l.strip() == '[Data]':
                    break
            else:
                # We never found a Data line
                raise Exception("No [Data] line in SampleSheet.csv")

            # Grab the header. Allow for a blank line
            res.append('[Data]')
            for l in ssfh:
                l = l.strip()
                if l:
                    data_headers = [ h.lower() for h in l.split(',') ]
                    res.append(l)
                    break
            else:
                # We never found the headers
                raise Exception("No headers after the [Data] line in SampleSheet.csv")

            try:
                lane_header_idx = data_headers.index('lane')
            except ValueError:
                # If there is no lane the semantics say that all lines apply to all lanes.
                lane_header_idx = None

            # Get the actual entries
            for l in ssfh:
                if not l.strip():
                    continue
                l = l.strip().split(',')
                if (lane_header_idx is None) or (l[lane_header_idx] == self.lane):
                    # Yeah we want this. But do we need any index munging?
                    if '1' in self.revcomp and 'index' in data_headers:
                        l[data_headers.index('index')] = revcomp(l[data_headers.index('index')])
                    if '2' in self.revcomp and 'index2' in data_headers:
                        l[data_headers.index('index2')] = revcomp(l[data_headers.index('index2')])

                    res.append(','.join(l))

        return res

    def load_samplesheet_ini(self):
        """Loads the [bcl2fastq] section from self._samplesheet into self.ini_settings,
           allowing things like --barcode-mismatches to be embedded in the SampleSheet.csv
        """
        cp = configparser.ConfigParser(empty_lines_in_values=False, delimiters=(':', '=', ' '))
        try:
            with open(self.samplesheet) as sfh:
                cp.read_file( takewhile(lambda x: not x.startswith('[Data]'),
                                        dropwhile(lambda x: not x.startswith('[bcl2fastq]'), sfh)),
                              self.samplesheet )

                for section in cp.sections():
                    # Cast all to strings
                    self.ini_settings[section].update(cp.items(section))
        except KeyError:
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

def revcomp(seq, ttable=str.maketrans('ATCG','TAGC')):
    """Standard revcomp
    """
    return seq.translate(ttable)[::-1]

def main(args):
    """ Main mainness
    """
    me = "Illuminatus " + os.path.basename(sys.argv[0])
    # This always comes out as a list of 1
    run_dir, = args.run_dir

    pp = BCL2FASTQPreprocessor(run_dir=run_dir, lane=args.lane, revcomp=args.revcomp)

    print( *pp.get_output(me), sep='\n' )

def parse_args():
    description = """Set up config for bcl2fastq for one lane"""

    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )

    argparser.add_argument("-r", "--revcomp", default=None, choices=[None, "", "1", "2", "12", "auto"],
                            help="Reverse complement index 2 and/or 1")
    argparser.add_argument("-l", "--lane", required=True, choices=list("12345678"),
                            help="Reverse complement index 2 and/or 1")
    argparser.add_argument("run_dir", nargs=1,
                            help="Directory containing the finished run")

    return argparser.parse_args()


if __name__ == '__main__':
    main(parse_args())
