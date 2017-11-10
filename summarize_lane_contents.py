#!/usr/bin/env python3
import sys, os
import datetime
import yaml
from argparse import ArgumentParser
from pprint import pprint, pformat

from illuminatus.SampleSheetReader import SampleSheetReader
from illuminatus.RunInfoXMLParser import RunInfoXMLParser

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
                        " of the form key=file where key is [wd, yield]")

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

    #See about extra stuff
    for ai in args.add_in_yaml:
        try:
            key, filename = ai.split('=', 1)

            if not key in ["wd", "yield"]:
                exit("Key for add_in_yaml must be wd or yield.")

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
    table_formats = ["",     "{:s}",    "{:s}",         "{:d}",        "{:s}",          "{:s}"           ]

    if 'add_in_yield' in rids:
        table_headers.extend(["Clusters PF", "Q30 (%)", "Yield GB"])
        table_formats.extend(["{:d}",        "{:.3f}",  "{:.3f}"  ])
    if 'add_in_wd' in rids:
        table_headers.extend(["Well Dups (%)"])
        table_formats.extend(["{:.2f}"       ])

    # col1_header is actually col0_header!
    mqc_out['pconfig']['col1_header'] = table_headers[0]
    for colnum, col in list(enumerate(table_headers))[1:]:
        mqc_out['headers']['col_{:02}'.format(colnum)] = dict(title=col, format=table_formats[colnum])

    for lane in rids['Lanes']:
        #Logic here is just copied from output_tsv, but we also want the total num_indexes
        #like in output_txt.
        #First put all the pools in one dict (not by project)
        pools_union = {k: v for d in lane['Contents'].values() for k, v in d.items()}
        num_indexes = sum(len(v) for v in pools_union.values())
        contents_str = ','.join( squish_project_content( pools_union , 5) )

        dd = mqc_out['data']['Lane {}'.format(lane['LaneNumber'])] = dict(
                                    col_01 = ','.join( sorted(lane['Contents']) ),
                                    col_02 = contents_str,
                                    col_03 = num_indexes,
                                    col_04 = lane['Loading'].get('pmol', 'unknown'),
                                    col_05 = lane['Loading'].get('phix', 'unknown') )

        if 'add_in_yield' in rids:
            #table_headers.extend(["Clusters PF", "Q30 (%)", "Yield"])
            lane_yield_info = rids['add_in_yield']['lane{}'.format(lane['LaneNumber'])]['Totals']
            dd['col_06'] = lane_yield_info['reads_pf']
            dd['col_07'] = lane_yield_info['percent_gt_q30']
            dd['col_08'] = lane_yield_info['yield_g']

        if 'add_in_wd' in rids:
            #table_headers.extend(["Well Dups (%)"])
            # This will be the last header. We'll have to do this properly if I add more
            # extras categories.
            lane_wd_info = rids['add_in_wd']['{}'.format(lane['LaneNumber'])]['mean']
            dd[max(mqc_out['headers'])] = lane_wd_info['raw']

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
    ss_lanes = [ line[ss_csv.column_mapping['lane']] for line in ss_csv.samplesheet_data ]
    for lanenum in sorted(set(ss_lanes)):
        thislane = {'LaneNumber': lanenum}

        #Add lane loading. In reality we probably need to get all lanes in one fetch,
        #but here's a placeholder.
        thislane['Loading'] = get_lane_loading(rids['Flowcell'])


        thislane['Contents'] = summarize_lane(
                                 [ line for line in ss_csv.samplesheet_data
                                   if line[ss_csv.column_mapping['lane']] == lanenum ],
                                 ss_csv.column_mapping )

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

        #I think this is what we are calling samples without a pool in the SSG
        #This definitely needs to be standardised.
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

            contents_str = ' '.join(squish_project_content(pools))

            contents_label = 'Libraries' if set(pools.keys()) == [''] else \
                             'Contents' if pools.get('') else \
                             'Pool' if len(pools) == 1 else 'Pools'

            p( "    - Project {p} -- {cl} {l} -- Number of indexes {ni} ".format(
                                p  = project,
                                l  = contents_str,
                                cl = contents_label,
                                ni = sum( len(p) for p in pools ) ) )
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
                               url  = "http://foo.example.com/" + name_match[0] )
            else:
                res[p] = dict( name = p + "_UNKNOWN" )
    else:
        try:
            from illuminatus.LIMSQuery import get_project_names

            for p, n in zip(proj_id_list, get_project_names(*proj_id_list)):
                if n:
                    res[p] = dict( name = n,
                                   url = "http://foo.example.com/" + n )
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
