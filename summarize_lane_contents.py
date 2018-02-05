#!/usr/bin/env python3
import sys, os
import datetime
import yaml
from argparse import ArgumentParser
#from pprint import pprint, pformat

from illuminatus.SampleSheetReader import SampleSheetReader
from illuminatus.RunInfoXMLParser import RunInfoXMLParser
from illuminatus.Formatters import pct

# Project links can be set by an environment var, presumably in environ.sh
PROJECT_PAGE_URL = os.environ.get('PROJECT_PAGE_URL', "http://foo.example.com/")
try:
    if PROJECT_PAGE_URL.format('test') == PROJECT_PAGE_URL:
        PROJECT_PAGE_URL += '{}'
except Exception:
    print("The environment variable PROJECT_PAGE_URL={} is not a valid format string.".format(
                PROJECT_PAGE_URL), file=sys.stderr)
    raise

def parse_args():
    description = """This script is part of the Illuminatus pipeline.
It makes the Samplesheet report that was previously handled by
wiki-communication/bin/upload_run_info_on_wiki.py, by parsing the SampleSheet.csv
and RunInfo.xml in the current directory and by asking the LIMS for proper project
names.
Output may be in YAML, MQC,  TSV or Text format. MQC is suitable for MultiQC custom
content - http://multiqc.info/docs/#custom-content.
Soon it will ask the LIMS for additional details (loading conc) too.
"""

# Note there is also RunMetaData.py and RunStatus.py which do similar jobs but this should
# be the only script that is querying the LIMS and looking at the details of the SampleSheet
# lines.

    a = ArgumentParser(description=description)
    a.add_argument("--project_name_list",
                   help="Supply a comma-separated list of project names." +
                        " If you do this, the LIMS will not be queried." +
                        " You can equivalently setenv PROJECT_NAME_LIST." )
    a.add_argument("--from_yml",
                   help="Get the info from the supplied YAML file, not by" +
                        " scanning the directory and the LIMS." )
    a.add_argument("--yml",
                   help="Output in YAML format to the specified file (- for stdout)." )
    a.add_argument("--mqc",
                   help="Output for MultiQC to the specified file (- for stdout)." )
    a.add_argument("--txt",
                   help="Output in text format to the specified file (- for stdout)." )
    a.add_argument("--tsv",
                   help="Output in TSV format to the specified file (- for stdout)." )
    a.add_argument("--add_in_yaml", nargs="*",
                   help="Add columns by sucking in etra bits of YAML. Items must be" +
                        " of the form key=file where key is [wd, yield, b2f]")

    a.add_argument("run_dir", nargs='?', default='.',
                   help="Supply a directory to scan, if not the current directory.")

    return a.parse_args()

def printable_date():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def main(args):
    """Basic gist - build data structure in memeory, then serialize it as
       requested.
    """
    #Sanity check that some output mode is active.
    if not any([args.yml, args.mqc, args.txt, args.tsv]):
        exit("No output specified. Nothing to do.")

    #See where we want to get our info
    try:
        if args.from_yml:
            if args.from_yml == '-':
                data_struct = yaml.safe_load(sys.stdin)
            else:
                with open(args.from_yml) as yfh:
                    data_struct = yaml.safe_load(yfh)
        else:
            pnl = args.project_name_list or os.environ.get('PROJECT_NAME_LIST', '')
            data_struct = scan_for_info( args.run_dir,
                                         project_name_list = pnl )
    except FileNotFoundError as e:
        exit("Error summarizing run.\n{}".format(e) )

    #See about extra stuff that we learn as processing goes on
    for ai in (args.add_in_yaml or []):
        try:
            key, filename = ai.split('=', 1)

            if not key in ["wd", "yield", "b2f"]:
                exit("Key for add_in_yaml must be wd, b2f or yield.")

            if not filename:
                #Empty val can be an artifact of the way Snakemake is calling this script
                continue

            with open(filename) as gfh:
                data_struct['add_in_' + key] = yaml.safe_load(gfh)

        except ValueError:
            exit("Error parsing {} as add_in_yaml.".format(ai))

    #See where we want to put it...
    for dest, formatter in [ ( args.yml, output_yml ),
                             ( args.mqc, output_mqc ),
                             ( args.txt, output_txt ),
                             ( args.tsv, output_tsv ) ]:
        if dest:
            if dest == '-':
                formatter(data_struct, sys.stdout)
            else:
                with open(dest, 'w') as ofh:
                    formatter(data_struct, ofh)

    #DONE!

def output_yml(rids, fh):
    """Simply dump the whole data structure as YAML
    """
    print(yaml.safe_dump(rids, default_flow_style=False), file=fh, end='')

def output_mqc(rids, fh):
    """This also happens to be YAML but is specifically for display
       in MultiQC. The filename should end in _mqc.yaml (not .yml) in
       order to be picked up.
    """
    mqc_out = dict(
        id           = 'lane_summary',
        section_name = 'Lane Summary',
        description  = 'Content of lanes in the run',
        plot_type    = 'table',
        pconfig      = { 'title': '', 'sortRows': True, 'no_beeswarm': True },
        data         = {},
        headers      = {},
    )

    #So my understanding is that pconfig needs to be a list of
    #singleton dicts as {col_id: { conf_1: 'foo', conf_2: 'bar' }}
    #for colnum, col in enumerate(["Lane", "Project", "Pool/Library", "Loaded (pmol)", "Loaded PhiX (%)"]):
    #    mqc_out['pconfig'].append( { 'col_{:02}'.format(colnum) : dict() } )

    # Nope - apparently not. Had to read the source...
    # 'headers' needs to be a dict of { col_id: {title: ..., format: ... }
    table_headers = ["Lane", "Project", "Pool/Library", "Num Indexes", "Loaded (pmol)", "Loaded PhiX (%)"]
    table_formats = ["",     "{:s}",    "{:s}",         "{:,}",        "{:s}",          "{:s}"           ]
    table_desc =    [None,   None,      "Summary of lane contents. See per-lane pages for a full list.",
                                                        "Number of samples, or 0 for a single unindexed sample.",
                                                                       None,            None ]

    if 'add_in_yield' in rids:
        table_headers.extend(["Clusters PF", "PF (%)", "Q30 (%)", "Yield GB"])
        table_formats.extend(["{:,}",        "{:.3f}", "{:.3f}",  "{:.3f}"  ])
        table_desc.extend(   ["Count of clusters/wells passing filter",
                                             "Percent of clusters/wells passing filter",
                                                       "Percent of bases being Q30 or more",
                                                                  "Yield in Gigabases"  ])

        # Also tack on a grand total to the description line of the table:
        yield_totals = [ v['Totals'] for v in rids['add_in_yield'].values() ]
        mqc_out['description'] += ", with {:,} of {:,} clusters passing filter ({:.3f}%)".format(
                    sum(t['reads_pf'] for t in yield_totals),
                        sum(t['reads'] for t in yield_totals),
                            pct( sum(t['reads_pf'] for t in yield_totals), sum(t['reads'] for t in yield_totals) ))

    if 'add_in_wd' in rids:
        table_headers.extend(["Well Dups (%)"])
        table_formats.extend(["{:.2f}"       ])
        table_desc.extend(   ["Average well dups (raw figure from count_well_dups) over the lane"])
    if 'add_in_b2f' in rids:
        table_headers.extend(["Barcode Balance"])
        table_formats.extend(["{:.4f}"       ])
        table_desc.extend(   ["Barcode balance expressed in terms of CV (from bcl2fastq)"])

    # col1_header is actually col0_header!
    mqc_out['pconfig']['col1_header'] = table_headers[0]
    for colnum, col in list(enumerate(table_headers))[1:]:
        column_settings = dict(title=col, format=table_formats[colnum])
        # This is a bit of a hack, but if the header contains a '%' symbol set min and max
        # accordingly. Also add the description.:
        if '%' in col: column_settings.update(min=0, max=100)
        if 'Barcode Balance' in col: column_settings.update(min=0, max=1)
        if table_desc[colnum]: column_settings.update(description=table_desc[colnum])
        mqc_out['headers']['col_{:02}'.format(colnum)] = column_settings

    # As a special case, force the Pool/Library column to be treated as text.
    # I might be asked to make the full list of libs appear in the popup, but let's
    # not second guess that.
    mqc_out['headers']['col_02']['textcell'] = True

    for lane in rids['Lanes']:
        # Logic here is just copied from output_tsv, but we also want the total num_indexes
        # like in output_txt.
        # First put all the pools in one dict (not partitioned by project)
        pools_union = {k: v for d in lane['Contents'].values() for k, v in d.items()}
        num_indexes = 0 if lane.get('Unindexed') else sum(len(v) for v in pools_union.values())
        contents_str = ', '.join( squish_project_content( pools_union , 20) )

        dd = mqc_out['data']['Lane {}'.format(lane['LaneNumber'])] = dict(
                                    col_01 = ','.join( sorted(lane['Contents']) ),
                                    col_02 = contents_str,
                                    col_03 = num_indexes,
                                    col_04 = lane['Loading'].get('pmol', 'unknown'),
                                    col_05 = lane['Loading'].get('phix', 'unknown') )

        if 'add_in_yield' in rids:
            # was: table_headers.extend(["Clusters PF", "Q30 (%)", "Yield"])
            # now: table_headers.extend(["Clusters PF", "PF (%)", "Q30 (%)", "Yield"])
            lane_yield_info = rids['add_in_yield']['lane{}'.format(lane['LaneNumber'])]['Totals']
            dd['col_06'] = lane_yield_info['reads_pf']
            dd['col_07'] = pct(lane_yield_info['reads_pf'], lane_yield_info['reads'])
            dd['col_08'] = lane_yield_info['percent_gt_q30']
            dd['col_09'] = lane_yield_info['yield_g']

        if 'add_in_wd' in rids:
            #table_headers.extend(["Well Dups (%)"])
            # See at which index in the table this header has ended up...
            dd_col, = [ k for k, v in mqc_out['headers'].items() if v['title'].startswith("Well Dups") ]
            # Get the relevant dict from the YAML data file which is indexed by lane and surface
            lane_wd_info = rids['add_in_wd']['{}'.format(lane['LaneNumber'])]['mean']
            # Add the raw value for now - could choose v1 or v2 instead?
            dd[dd_col] = lane_wd_info['raw']

        if 'add_in_b2f' in rids:
            #table_headers.extend(["Barcode Balance"])
            dd_col, = [ k for k, v in mqc_out['headers'].items() if v['title'].startswith("Barcode Balance") ]
            # If all the entries are blank does MultiQC hide the column for me or do I need to
            # do that myself??
            if 'Barcode Balance' in rids['add_in_b2f'][int(lane['LaneNumber'])]:
                dd[dd_col] = rids['add_in_b2f'][int(lane['LaneNumber'])]['Barcode Balance']

    print(yaml.safe_dump(mqc_out, default_flow_style=False), file=fh, end='')

def scan_for_info(run_dir, project_name_list=''):
    """Hoovers up the info and builds a data structure which can
       be serialized to YAML.
    """
    # Load both the RunInfo.xml and the SampleSheet.csv
    ri_xml = RunInfoXMLParser(run_dir + "/RunInfo.xml")
    ss_csv = SampleSheetReader(run_dir + "/SampleSheet.csv")

    # Build run info data structure (rids). First just inherit the info
    # from ri_xml (RunId, Instrument, Flowcell)
    rids = ri_xml.run_info.copy()

    # Reads are pairs (length, index?)
    rids['CyclesAsList'] = [ (ri_xml.read_and_length[i], ri_xml.read_and_indexed[i] is 'Y')
                             for i in
                             sorted(ri_xml.read_and_length.keys(), key=int) ]

    #Which file is actually providing the SampleSheet?
    try:
        rids['SampleSheet'] = os.path.basename(os.readlink(run_dir + "/SampleSheet.csv"))
    except OSError:
        # Weird - maybe not a link?
        rids['SampleSheet'] = "SampleSheet.csv"

    #When is this  report being made?
    rids['ReportDateTime'] = printable_date()

    #Translate all the project numbers to names in one go
    #If you try to feed this script an old 2500 Sample Sheet this is where it will fail.
    assert not 'sampleproject' in ss_csv.column_mapping, \
        "A sampleproject (without the underscore) column was found. Is this an old 2500 SampleSheet?"
    rids['ProjectInfo'] = project_real_name(
                            set([ line[ss_csv.column_mapping['sample_project']]
                                  for line in ss_csv.samplesheet_data ]),
                            project_name_list )

    #Slice the sample sheet by lane
    rids['Lanes'] = []

    # NOTE - if a samplesheet has no 'lane' column then we shouldn't really be processing it,
    # but as far as bcl2fastq is concerned this just means all lanes are identical, so for
    # the purposes of this script I'll go with that.
    if 'lane' in ss_csv.column_mapping:
        ss_lanes = [ line[ss_csv.column_mapping['lane']] for line in ss_csv.samplesheet_data ]
    else:
        ss_lanes = [ str(x + 1) for x in range(int(rids['LaneCount'])) ]

    for lanenum in sorted(set(ss_lanes)):
        thislane = {'LaneNumber': lanenum}

        #Add lane loading. In reality we probably need to get all lanes in one fetch,
        #but here's a placeholder.
        thislane['Loading'] = get_lane_loading(rids['Flowcell'])

        lines_for_lane = [ line for line in ss_csv.samplesheet_data
                           if 'lane' not in ss_csv.column_mapping or
                              line[ss_csv.column_mapping['lane']] == lanenum ]

        thislane['Contents'] = summarize_lane( lines_for_lane, ss_csv.column_mapping )

        #If the lane contains a single sample, is that one barcode or is it unindexed?
        #We'd like to report which.
        if len(lines_for_lane) == 1:
            index_lengths = ss_csv.get_index_lengths_by_lane()[lanenum]
            #It's unindexed if there are no indices or if they contain only N's.
            thislane['Unindexed'] = not any( index_lengths )
        else:
            thislane['Unindexed'] = False

        rids['Lanes'].append(thislane)

    return rids

def summarize_lane(lane_lines, column_mapping):
    """Given a list of lines, summarize what they contain, returning
       a dict of { project: { pool: [ list of libs ] } }
       The caller is presumed to have filtered the lines by lane already.
    """
    #Make a dict of dicts keyed on all the projects seen
    res = dict()

    for line in lane_lines:
        sample_project = line[column_mapping['sample_project']]
        sample_id = line[column_mapping['sample_id']]

        #Pool and library should be combined in the sample_id
        if '__' in sample_id:
            sample_pool, sample_lib = sample_id.split('__')
        else:
            sample_pool, sample_lib = '', sample_id

        # I think this is what we are calling samples without a pool in the SSG, and
        # thus the subdirectory name that will be used for the output files.
        # This definitely needs to be standardised.
        if sample_pool == 'NoPool': sample_pool=''

        #Avoid use of defaultdict as it gums up YAML serialization. This is equivalent.
        res.setdefault(sample_project, dict()).setdefault(sample_pool, []).append(sample_lib)

    return res

def output_txt(rids, fh):
    p = lambda *a: print(*a, file=fh)

    #Basic metadata, followed be a per-lane summary.
    p( "Run ID: {}".format(rids['RunId']) )
    p( "Instrument: {}".format(rids['Instrument']) )
    p( "Read length: {}".format(rids['Cycles']) )
    p( "Active SampleSheet: SampleSheet.csv -> {}".format(rids['SampleSheet']) )
    p( "" )


    p("Samplesheet report at {}:".format(rids['ReportDateTime']))

    #Summarize each lane
    prn = rids['ProjectInfo']
    for lane in rids['Lanes']:
        p( "Lane {}:".format(lane['LaneNumber']) )

        for project, pools in sorted(lane['Contents'].items()):
            # pools will be a dict of poolname : [ library, ... ]

            # Special case for PhiX
            if project == 'ControlLane' and pools == {'': ['PhiX']}:
                p( "    - PhiX")

            else:

                contents_str = ' '.join(squish_project_content(pools))

                contents_label = 'Libraries' if list(pools) == [''] else \
                                 'Contents' if pools.get('') else \
                                 'Pool' if len(pools) == 1 else 'Pools'

                num_indexes = 0 if lane.get('Unindexed') else sum( len(p) for p in pools.values() )

                p( "    - Project {p} -- {cl} {l} -- Number of indexes {ni}".format(
                                    p  = project,
                                    l  = contents_str,
                                    cl = contents_label,
                                    ni = num_indexes ) )
                p( "    - See {link}".format(link = prn[project].get('url', prn[project]['name'])) )


def output_tsv(rids, fh):
    """TSV table for the run report.
    """
    p = lambda *a: print('\t'.join(a), file=fh)

    #Headers
    p("Lane", "Project", "Pool/Library", "Loaded (pmol)", "Loaded PhiX (%)")

    for lane in rids['Lanes']:

        #This time, squish content for all projects together when listing the pools.
        #If there are more than 5 things in the lane, abbreviate the list. Users can always look
        #at the detailed table.
        pools_union = {k: v for d in lane['Contents'].values() for k, v in d.items()}
        contents_str = ','.join( squish_project_content( pools_union , 5) )

        p( lane['LaneNumber'],
           ','.join( sorted(lane['Contents']) ),
           contents_str,
           lane['Loading'].get('pmol', 'unknown'),
           lane['Loading'].get('phix', 'unknown') )

def squish_project_content(dict_of_pools, maxlen=0):
    """Given a dict taken from rids['Lanes'][n]['Contents'] -- ie. a dict of pool: content_list
       returns a human-readable list of contents.
    """
    all_pools = sorted([ p for p in dict_of_pools if p ])
    non_pooled_libs = sorted(dict_of_pools.get('',[]))

    #Prune those lists
    if maxlen and len(all_pools) > maxlen:
        all_pools[maxlen-1:] = [ 'plus {} more pools'.format(len(all_pools) + 1 - maxlen) ]
    if maxlen and len(non_pooled_libs) > maxlen:
        non_pooled_libs[maxlen-1:] = [ 'plus {} more libraries'.format(len(non_pooled_libs) + 1 - maxlen) ]

    #Now return the lot.
    return all_pools + non_pooled_libs


def get_lane_loading(flowcell):
    """A placeholder. At some point this will query the LIMS for lane loading info -
       ie. pmol Loaded and PhiX %
       And we'll probably need to mock it out in the test cases.
    """
    return dict()

# A rather contorted way to get project names. We may be able to bypass
# this by injecting them straight into the sample sheet!
def project_real_name(proj_id_list, name_list=''):
    """Resolves a list of project IDs to a name and URL
    """
    res = dict()
    if name_list:
        name_list_split = name_list.split(',')
        # Resolve without going to the LIMS. Note that if you want to disable
        # LIMS look-up without supplying an actuall list of names you can just
        # say "--project_names dummy" or some such thing.
        for p in proj_id_list:
            name_match = [ n for n in name_list_split if n.startswith(p) ]
            if len(name_match) == 1:
                res[p] = dict( name = name_match[0],
                               url  = PROJECT_PAGE_URL.format(name_match[0]) )
            elif p == "ControlLane":
                res[p] = dict( name = p )
            else:
                res[p] = dict( name = p + "_UNKNOWN" )
    else:
        # Go to the LIMS. The current query mode hits the database as configured
        # by ~/.genologicsrc.
        try:
            from illuminatus.LIMSQuery import get_project_names

            for p, n in zip(proj_id_list, get_project_names(*proj_id_list)):
                if n:
                    res[p] = dict( name = n,
                                   url = PROJECT_PAGE_URL.format(n) )
                elif p == "ControlLane":
                    res[p] = dict( name = p )
                else:
                    res[p] = dict( name = p + "_UNKNOWN" )
        except Exception as e:
            for p in proj_id_list:
                if p not in res:
                    res[p] = dict( name = p + "_LOOKUP_ERROR",
                                   url = "error://" + repr(e) )

    return res

if __name__ == "__main__":
    main(parse_args())
