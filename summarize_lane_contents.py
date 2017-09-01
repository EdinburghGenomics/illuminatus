#!/usr/bin/env python3
import sys, os
import datetime
import yaml
from argparse import ArgumentParser

from illuminatus.SampleSheetReader import SampleSheetReader
from illuminatus.RunInfoXMLParser import RunInfoXMLParser

def parse_args():
    description = """This script is part of the Illuminatus pipeline.
It makes the Samplesheet report that was previously handled by
wiki-communication/bin/upload_run_info_on_wiki.py, by parsing the SampleSheet.csv
and RunInfo.xml in the current directory and by asking the LIMS for proper project
names.
Output may be in YAML, TSV or Text format.
Soon it will ask the LIMS for additional details (loading conc) too.
"""

#Note there is also RunMetaData.py and RunInfo.py which do similar jobs but this should
#be the only script that is querying the LIMS and looking at the details of the SampleSheet
#lines.

    a = ArgumentParser(description=description)
    a.add_argument("--project_name_list",
                   help="Supply a comma-separated list of project names." +
                        " If you do this, the LIMS will not be queried." +
                        " You can equivalently setenv PROJECT_NAME_LIST." )
    a.add_argument("--from_yml",
                   help="Get the info from the supplied YAML file, not by" +
                        "scanning the directory and the LIMS." )
    a.add_argument("--yml",
                   help="Output in YAML format to the specified file (- for stdout)." )
    a.add_argument("--txt",
                   help="Output in text format to the specified file (- for stdout)." )
    a.add_argument("--tsv",
                   help="Output in TSV format to the specified file (- for stdout)." )

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
    if not any([args.yml, args.txt, args.tsv]):
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
            data_struct = scan_for_info(args.run_dir)
    except FileNotFoundError as e:
        exit("Error summarizing run.\n{}".format(e) )

    #See where we want to put it...
    for dest, formatter in [ ( args.yml, output_yml ),
                             ( args.txt, output_txt ),
                             ( args.tsv, output_tsv ) ]:
        if dest:
            if dest == '-':
                formatter(data_struct, sts.stdout)
            else:
                with open(dest, 'w') as ofh:
                    formatter(data_struct, ofh)

    #DONE!

def output_yaml(rid, fh):
    print(yaml.safe_dump(conf, default_flow_style=False), file=fh)

def scan_for_info(run_dir):
    """Hoovers up the info and builds a data structure which can
       be serialized to YAML.
    """
    # Load both the RunInfo.xml and the SampleSheet.csv
    ri_xml = RunInfoXMLParser(args.run_dir + "/RunInfo.xml")
    ss_csv = SampleSheetReader(args.run_dir + "/SampleSheet.csv")

    # Build run info data structure (rids). First just inherit the info
    # from ri_xml (RunId, Instrument, FlowCell)
    rids = ri_xml.run_info.copy()

    # Reads are pairs (length, index?)
    rids['CyclesAsList'] = [ (ri_xml.read_and_length[i], ri_xml.read_and_indexed[i] is 'Y')
                             for i in
                             sorted(ri_xml.read_and_length.keys(), key=int) ]

    #Which file is actually providing the SampleSheet?
    rids['SampleSheet'] = os.path.basename(os.readlink(args.run_dir + "/SampleSheet.csv"))

    #When is this  report being made?
    rids['ReportDateTime'] = printable_date()

    #Translate all the project numbers to names in one go
    project_name_list = ( args.project_name_list or os.environ.get('PROJECT_NAME_LIST', '') )
    rids['ProjectInfo'] = project_real_name(
                            set([ line[ss_csv.column_mapping['sample_project']]
                                  for line in ss_csv.samplesheet_data ]),
                            project_name_list.split(',') )

    #Add lane loading
    rids['Loading'] = get_lane_loading(rids['FlowCell'])

    #Slice the sample sheet by lane
    rid['Lanes'] = []
    ss_lanes = [ line[ss_csv.column_mapping['lane']] for line in ss_csv.samplesheet_data ]
    for lanenum in sorted(set(ss_lanes)):
        thislane = {'LaneNumber': lanenum}

        thislane['Contents'] = summarize_lane(
                                 [ line for line in ss_csv.samplesheet_data
                                   if line[ss_csv.column_mapping['lane']] == lanenum ],
                                 ss_csv.column_mapping )

        rid['Lanes'].append(thislane)


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
        if sample_pool == 'NoPool': sample_pool=''

        #Avoid use of defaultdict as it gums up YAML serialization. This is equivalent.
        res.setdefault(sample_project, dict()).setdefault(sample_pool, []).append(sample_lib)

    return res

def output_txt(rids, fh):
    p = lambda *a: print(*a, file=fh)

    #Basic metadata, followed be a per-lane summary.
    p( "Run ID: {}".format(rids['RunId']) )
    p( "Instrument: {}".format(rids['Instrument']) )
    p( "Read length: {}".format(','.join(
                                 [ ('[{}]' if r[1] else '{}').format(r[0])
                                   for r in rids['Reads'] ] ))
    p( "Active SampleSheet: SampleSheet.csv -> {}".format(rids['SampleSheet']) )
    p( "" )


    p("Samplesheet report at {}:".format(rids['ReportDateTime']))

    #Summarize each lane
    prn = rids['ProjectInfo']
    for lane in rid['Lanes']:
        p( "Lane {}:".format(lane['LaneNumber']) )

        for project, pools in sorted(lane['Contents'].items()):

            contents_str = ','.join(squish_project_content(pools))

            p( "    - Project {p} -- Library {l} -- Number of indexes {ni} ".format(
                                p  = project,
                                l  = contents_str,
                                ni = sum( len(p) for p in pools ) ) )
            p( "    - See {link}".format(link = prn[project].get('url', prn[project]['name'])) )


output_tsv(rids, fh):
    """TSV table for the run report.
    """
    p = lambda *a: print(*a, file=fh)

    #Headers
    p(["Lane", "Project", "Pool/Library", "Loaded (pmol)", "Loaded PhiX (%)"].join("\t"))

    for lane in rid['Lanes']:

        #This time, squish content for all projects together when listing the pools.
        #If there are more than 5 things in the lane, abbreviate the list. Users can always look
        #at the detailed table.
        pools_union = {k: v for d in lane['Contents'].values() for k, v in d.items()}
        contents_str = ','.join( squish_project_content( pools_union , 5) )

        p( [ lane['LaneNumber'],
             ','.join( sorted(lane['Contents']) ),
             contents_str,
             lane['Loading'].get('pmol', 'unknown'),
             lane['Loading'].get('phix', 'unknown')  )

def squish_project_contents(dict_of_pools, maxlen=0):
    """Given a dict taken from rid['Lanes'][n]['Contents'] -- ie. a dict of pool: content_list
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
    """
    return dict()

# A rather contorted way to get project names. We may be able to bypass
# this by injecting them straight into the sample sheet!
def project_real_name(proj_id_list, name_list=None):
    """Resolves a list of project IDs to a name and URL
    """
    res = dict()
    if name_list:
        # Resolve without going to the LIMS. Note that if you want to disable
        # LIMS look-up without supplying an actuall list of names you can just
        # say "--project_names dummy" or some such thing.
        for p in proj_id_list:
            name_match = [ n for n in name_list if n.startswith(p) ]
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
                                   url = "http://foo.example.com/" + name_match[0] )
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
