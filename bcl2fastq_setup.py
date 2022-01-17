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
    def __init__(self, run_source_dir, **kwargs):

        #Read data_dir and check that requested lane is in the SampleSheet.
        self.run_dir = run_source_dir

        self.samplesheet = os.path.join(self.run_dir, "SampleSheet.csv")
        self.runinfo_file = os.path.join(self.run_dir, "RunInfo.xml")

        # This code is a little crufty but is tested and working.
        self.bme = BaseMaskExtractor(self.samplesheet, self.runinfo_file)

        # Get the run name and tiles list from the RunInfo.xml
        rip = RunInfoXMLParser( self.run_dir )
        self.run_info = rip.run_info
        self.tiles = rip.tiles

        # Check the lane is valid.
        self.lane = str(kwargs['lane'])
        assert self.bme.get_lanes(), \
            "SampleSheet.csv does not seem to list any lanes."
        assert self.lane  in [ str(l) for l in self.bme.get_lanes() ], \
            "{!r} not in {!r}".format(self.lane, self.bme.get_lanes())

        # This sets up self.ini_settings()
        self.get_ini_settings()

        # See if we want to revcomp at all
        if kwargs['revcomp'] == 'auto':
            self.revcomp = self.infer_revcomp()
            self.revcomp_label = 'auto ' + (self.revcomp or 'none')
        elif not kwargs['revcomp']:
            self.revcomp = ''
            self.revcomp_label = 'none'
        elif kwargs['revcomp'] == 'none':
            # Explicitly none as opposed to implicitly none
            self.revcomp = ''
            self.revcomp_label = 'override none'
        else:
            self.revcomp = kwargs['revcomp']
            self.revcomp_label = 'override ' + self.revcomp

        # Save bc_check flag
        self.bc_check = kwargs.get('bc_check', False)

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
                        os.path.join(self.run_dir, "pipeline_settings.lane{}.ini".format(self.lane)) ) ]:
            i()

            # Special case for barcode-mismatches, even though we'll normally do this by retry.
            for k in list(self.ini_settings['bcl2fastq'].keys()):
                # Per-lane --barcode-mismatches overrides the default
                if k == '--barcode-mismatches-lane{}'.format(self.lane):
                    self.ini_settings['bcl2fastq']['--barcode-mismatches'] = \
                        self.ini_settings['bcl2fastq'][k]
                # delete it and any other per-lane vals to avoid further processing
                if k.startswith('--barcode-mismatches-'):
                    del self.ini_settings['bcl2fastq'][k]

    def get_bcl2fastq_opt_dict(self):
        """Get the options which will go into the [bcl2fastq] section on the sample sheet.
           Unlike get_ini_settings() this does not set a variable on the object but just returns
           a dictionary of options.
        """
        bcl2fastq_opts = {"--fastq-compression-level": "6"}

        # Add base mask for this lane
        bm = self.bme.get_base_mask_for_lane(self.lane)
        bcl2fastq_opts["--use-bases-mask"] = "'{}'".format(bm)

        # Specify the lane to process, which is controlled by --tiles
        # Note that $LANE is going to be interpreted by the shell when the command is run.
        # Slimmed-down runs override this setting but will still include $LANE to pick up the lane number
        bcl2fastq_opts["--tiles"] = "'s_[{}]'".format(self.lane)

        # now that the bcl2fastq_opts array is complete, evaluate the pipeline_settings.ini file
        # and update the dict
        bcl2fastq_opts.update(self.ini_settings['bcl2fastq'].items())

        return bcl2fastq_opts

    def get_bcl2fastq_options(self):
        opts_dict = self.get_bcl2fastq_opt_dict()
        return ['{} {}'.format(*o) for o in opts_dict.items()]

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

    def get_bc_check_opts(self):
        """Return a modified list of options suitable for the barcode check phase,
           which can be run immediately after the final index cycle.
        """
        # Get the regular options
        check_opts = self.get_bcl2fastq_opt_dict()

        check_opts['--interop-dir'] = '.'
        check_opts['--minimum-trimmed-read-length'] = '1'

        # Tricky ones are --tiles and --use-bases-mask
        # For --tiles we'll take the first tile (alphabetically) in self.run_info or else
        # assume that tile 1101 is valid (which works for MiSeq runs)
        if self.tiles:
            tiles_for_lane = [ t for l, t in
                               [ t.split('_') for t in self.tiles ]
                               if l == self.lane ]
            check_opts['--tiles'] = "'s_[{}]_{}'".format(self.lane, tiles_for_lane[0])
        else:
            check_opts["--tiles"] = "'s_[{}]_1101'".format(self.lane)

        # Base mask needs some munging. We should always have an initial version, but it could be
        # supplied from outside so a little sanity checking is necessary.
        old_bm = check_opts["--use-bases-mask"].strip("'")
        if ':' in old_bm:
            assert old_bm.startswith("{}:".format(self.lane))
            old_bm = old_bm[2:]
        new_bm = ','.join([ ('n*' if i else 'Yn*') if m.startswith('Y') else m
                            for i, m in enumerate(old_bm.split(',')) ])
        check_opts["--use-bases-mask"] = "'{}'".format(new_bm)

        return ['{} {}'.format(*o) for o in check_opts.items()]

    def get_output(self, me):
        """Return a new partial sample sheet as a list of lines.
        """
        res = ['[Header]']

        if not self.bc_check:
            # Calculate the bcl2fastq_opts:
            # work out all the options including --barcode-mismatches which is special.
            bcl2fastq_opts = self.get_bcl2fastq_options()
        else:
            # For bc_check mode we want to fudge some of those
            bcl2fastq_opts = self.get_bc_check_opts()

        # OK now we can go through the input sample sheet.
        with open(self.run_dir + '/SampleSheet.csv') as ssfh:
            # Allow for blank lines and comments at the top
            for l in ssfh:
                l = l.strip()
                if l and (not l.startswith('#')):
                    break
            # We expect to have a [Header] section.
            assert l == '[Header]'
            for l in ssfh:
                l = l.strip()
                if l == '' or l.startswith('['):
                    break
                if not any(l.startswith(x) for x in ('Description', '#')):
                    res.append(l)
            res.append("Run ID,{}".format(self.run_info['RunId']))
            res.append("Description,Fragment processed with {}".format(me))
            res.append("#Lane,{}".format(self.lane))
            res.append("#Revcomp,{}".format(self.revcomp_label))

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
    this_script = "Illuminatus " + os.path.basename(sys.argv[0])
    # This always comes out as a list of 1
    run_dir, = args.run_dir

    pp = BCL2FASTQPreprocessor(run_source_dir=run_dir, **vars(args))

    print( *pp.get_output(this_script), sep='\n' )

def parse_args():
    description = """Outputs a sample sheet fragment for bcl2fastq for one lane"""

    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )

    argparser.add_argument("-r", "--revcomp", default="", choices=["none", "", "1", "2", "12", "auto"],
                            help="Reverse complement index 2 and/or 1")
    argparser.add_argument("-l", "--lane", required=True, choices=list("12345678"),
                            help="Lane to be demultiplexed")
    argparser.add_argument("-c", "--bc_check", action="store_true",
                           help="Prepare for barcode check mode (1 tile 1 base)")
    argparser.add_argument("run_dir", nargs=1,
                            help="Directory containing the finished run")

    return argparser.parse_args()


if __name__ == '__main__':
    main(parse_args())
