#!/usr/bin/env python3
import sys, os
import datetime
import yaml, yamlloader
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from illuminatus.SampleSheetReader import SampleSheetReader
from illuminatus.RunInfoXMLParser import RunInfoXMLParser
from illuminatus.RunParametersXMLParser import RunParametersXMLParser
from illuminatus.Formatters import pct, fmt_time

# Project links can be set by an environment var, presumably in environ.sh
PROJECT_PAGE_URL = os.environ.get('PROJECT_PAGE_URL', "http://foo.example.com/")
try:
    if PROJECT_PAGE_URL.format('test') == PROJECT_PAGE_URL:
        PROJECT_PAGE_URL += '{}'
except Exception:
    print(f"The environment variable PROJECT_PAGE_URL={PROJECT_PAGE_URL} is not a valid format string.",
          file = sys.stderr)
    raise

# Non-pools may either be called 'NoPool' or ''. Other names may be added here.
NON_POOLS = ['NoPool', 'None', '']

def parse_args(*args):
    description = """This script is part of the Illuminatus pipeline.
It gathers an overview of the run by parsing the SampleSheet.csv, RunParameters.xml
and RunInfo.xml in the current directory and by asking the LIMS for proper project
names.
Output may be in YAML, MQC,  TSV or Text format. MQC is suitable for MultiQC custom
content - http://multiqc.info/docs/#custom-content. YAML may be re-loaded and re-presented
as any format.
Soon it should ask the LIMS for additional details (eg. loading conc) too.
"""

# Note that summarize_for_overview.py now obtains much of the information from the YAML
# outputted form this script. Possibly the functionality should be folded in here? One
# reason to not do that is that a few things are always checked dynamically by that script,
# but the shtick of this script is that any output format can be created purely from the YAML,
# and the YAML is only dependent on the sample sheet and run metadata files.

    a = ArgumentParser( description=description,
                        formatter_class = ArgumentDefaultsHelpFormatter )
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
                   help="Add columns by sucking in extra bits of YAML. Items must be" +
                        " of the form key=file where key is [wd, yield, b2f]")

    a.add_argument("run_dir", nargs='?', default='.',
                   help="Supply a directory to scan, if not the current directory.")

    return a.parse_args(*args)

def main(args):
    """Basic gist - build data structure in memory, then serialize it as
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
        exit(f"Error summarizing run.\n{e}")

    #See about extra stuff that we learn as processing goes on
    for ai in (args.add_in_yaml or []):
        try:
            key, filename = ai.split('=', 1)

            if key not in ["wd", "yield", "b2f"]:
                exit("Key for add_in_yaml must be wd, b2f or yield.")

            if not filename:
                #Empty val can be an artifact of the way Snakemake is calling this script
                continue

            with open(filename) as gfh:
                data_struct['add_in_' + key] = yaml.safe_load(gfh)

        except ValueError:
            exit(f"Error parsing {ai} as add_in_yaml.")

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
    print( yaml.dump( rids,
                      Dumper = yamlloader.ordereddict.CSafeDumper,
                      default_flow_style = False),
           file = fh,
           end = '' )

def output_mqc(rids, fh):
    """This also happens to be YAML but is specifically for display
       in MultiQC. The filename should end in _mqc.yaml (not .yml) in
       order to be picked up.
    """
    # Decide if this is a MiSeq (non-patterned flowcell). This will determine
    # exactly what is displayed.
    is_patterned_flowcell = not ( rids['Instrument'].startswith('hiseq2500') or
                                  rids['Instrument'].startswith('miseq') )

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
    #for colnum, col in enumerate(["Lane", "Project", "Pool/Library", "Loaded (pmol)"]):
    #    mqc_out['pconfig'].append( { 'col_{:02}'.format(colnum) : dict() } )

    # Nope - apparently not. Had to read the source...
    # 'headers' needs to be a dict of { col_id: {title: ..., format: ... }
    table_headers = ["Lane", "Project", "Pool/Library", "Num Indexes", "Loaded (pmol)"]
    table_formats = ["",     "{:s}",    "{:s}",         "{:,}",        "{:s}",        ]
    table_desc =    [None,   None,      "Summary of lane contents. See per-lane pages for a full list.",
                                                        "Number of samples, or 0 for a single unindexed sample.",
                                                                       None,          ]

    # We'll always add the density column but will hide it later for patterned flowcells
    if 'add_in_yield' in rids:
        table_headers.extend(["Aligned PhiX (%)", "Density", "Clusters PF", "PF (%)", "Q30 (%)", "Yield GB"])
        table_formats.extend(["{:.3f}",           "{:,.1f}", "{:,}",        "{:.3f}", "{:.3f}",  "{:.3f}"  ])
        table_desc.extend(   ["Percentage of PhiX according to InterOp",
                                                  "Raw cluster density according to InterOp",
                                                             "Count of clusters/wells passing filter",
                                                                            "Percent of clusters/wells passing filter",
                                                                                      "Percent of bases being Q30 or more",
                                                                                                 "Yield in Gigabases"  ])

    # Also tack on a grand total to the description line above the table,
    # unless we have the more accurate b2f values available.
    if 'add_in_yield' in rids and 'add_in_b2f' not in rids:
        yield_totals = [ rids['add_in_yield'][f"lane{lane['LaneNumber']}"]['Totals'] for lane in rids['Lanes'] ]
        mqc_out['description'] += ", with {:,} of {:,} clusters passing filter, according to InterOP ({:.3f}%)".format(
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

        # Tack on a grand total to the description line of the table, using the
        # more accurate values than we have from interop.
        yield_totals = [ rids['add_in_b2f'][int(lane['LaneNumber'])] for lane in rids['Lanes'] ]
        grand_total_raw = sum(t.get('Total Reads Raw') for t in yield_totals)
        grand_total_pf = sum(t.get('Assigned Reads',0) + t.get('Unassigned Reads PF',0) for t in yield_totals)
        mqc_out['description'] += ", with {:,} of {:,} clusters passing filter, according to bcl2fastq ({:.3f}%)".format(
                                          grand_total_pf,
                                                  grand_total_raw,
                                                                    pct( grand_total_pf, grand_total_raw ))

    # Here we tweak the settings for our table columns.
    # col1_header is actually col0_header!
    mqc_out['pconfig']['col1_header'] = table_headers[0]
    for colnum, col in list(enumerate(table_headers))[1:]:
        column_settings = dict(title=col, format=table_formats[colnum])
        # This is a bit of a hack, but if the header contains a '%' symbol set min and max
        # accordingly. Also add the description.:
        if '%' in col: column_settings.update(min=0, max=100)
        if 'Barcode Balance' in col: column_settings.update(min=0, max=1)
        if 'Density' in col and is_patterned_flowcell: column_settings.update(hidden=True)

        if table_desc[colnum]: column_settings.update(description=table_desc[colnum])
        mqc_out['headers'][f"col_{colnum:02}"] = column_settings

    # As a special case, force the Pool/Library column to be treated as text.
    # I might be asked to make the full list of libs appear in the popup, but let's
    # not second guess that.
    # Also the same for the Project column as ther may be many
    mqc_out['headers']['col_01']['textcell'] = True # Project
    mqc_out['headers']['col_02']['textcell'] = True # Pool/Library

    for lane in rids['Lanes']:
        # Logic here is just copied from output_tsv, but we also want the total num_indexes
        # like in output_txt.
        # First put all the pools in one dict (not partitioned by project)
        pools_union = dict_union(lane['Contents'].values())
        num_indexes = 0 if lane.get('Unindexed') else sum(len(v) for v in pools_union.values())
        contents_str = ', '.join( squish_project_content( pools_union , 20) )

        dd = mqc_out['data'][f"Lane {lane['LaneNumber']}"] = dict(
                                    col_01 = ','.join( sorted(lane['Contents']) ),
                                    col_02 = contents_str,
                                    col_03 = num_indexes,
                                    col_04 = lane['Loading'].get('pmol', 'unknown') )

        if 'add_in_yield' in rids:
            # was: table_headers.extend(["Clusters PF", "Q30 (%)", "Yield"])
            # now: table_headers.extend(["Clusters PF", "PF (%)", "Q30 (%)", "Yield GB"])
            lane_yield_info = rids['add_in_yield'][f"lane{lane['LaneNumber']}"]['Totals']
            dd['col_05'] = lane_yield_info.get('percent_aligned', 'unknown')
            dd['col_06'] = lane_yield_info['density']
            dd['col_07'] = lane_yield_info['reads_pf']
            dd['col_08'] = pct(lane_yield_info['reads_pf'], lane_yield_info['reads'])
            dd['col_09'] = lane_yield_info['percent_gt_q30']
            dd['col_10'] = lane_yield_info['yield_g']

        if 'add_in_wd' in rids:
            #table_headers.extend(["Well Dups (%)"])
            # See at which index in the table this header has ended up...
            dd_col, = [ k for k, v in mqc_out['headers'].items() if v['title'].startswith("Well Dups") ]
            # Get the relevant dict from the YAML data file which is indexed by lane and surface
            lane_wd_info = rids['add_in_wd'][f"{lane['LaneNumber']}"]['mean']
            # Add the raw value for now - could choose v1 or v2 instead?
            dd[dd_col] = lane_wd_info['raw']

        if 'add_in_b2f' in rids:
            #table_headers.extend(["Barcode Balance"])
            dd_col, = [ k for k, v in mqc_out['headers'].items() if v['title'].startswith("Barcode Balance") ]
            lane_b2f_totals = rids['add_in_b2f'][int(lane['LaneNumber'])]

            # If all the entries are blank does MultiQC hide the column for me or do I need to
            # do that myself?? Or do I even want to?
            if 'Barcode Balance' in lane_b2f_totals:
                dd[dd_col] = lane_b2f_totals['Barcode Balance']

            # If b2f data is provided, use the more accurate yield numbers for 'reads_pf', overwriting
            # those from interop.
            if 'add_in_yield' in rids:
                dd['col_07'] = lane_b2f_totals.get('Assigned Reads',0) + lane_b2f_totals.get('Unassigned Reads PF',0)


    print( yaml.dump( mqc_out,
                      Dumper = yamlloader.ordereddict.CSafeDumper,
                      default_flow_style = False ),
           file = fh,
           end='' )

def scan_for_info(run_dir, project_name_list=''):
    """Hoovers up the info and builds a data structure which can
       be serialized to YAML.
    """
    # Load both the RunInfo.xml and (a little later) the SampleSheet.csv
    ri_xml = RunInfoXMLParser(run_dir)

    # Build run info data structure (rids). First just inherit the info
    # from ri_xml (RunId, Instrument, Flowcell, ...)
    rids = ri_xml.run_info.copy()

    # We need this to reliably get the NovoSeq flowcell type
    # Also we now care about the experiment name which is here and lets us link to BaseSpace
    try:
        run_params = RunParametersXMLParser( run_dir ).run_parameters
        if 'Flowcell Type' in run_params:
            rids['FCType'] = run_params['Flowcell Type']
        rids['ExperimentName'] = run_params.get('Experiment Name')
        # This 'Start Time' comes from file timestamps. RunDate on the NovaSeq also
        # gives a timestamp, but not on the MiSeq, even post-upgrade. And I don't
        # trust the MiSeq clock in any case.
        rids['RunStartTimeStamp'] = run_params.get('Start Time')
        rids['RunStartTime'] = fmt_time(rids['RunStartTimeStamp'])

        rids['Chemistry'] = get_chemistry(run_params, rids['Instrument'])
    except Exception:
        # Not to worry we can do without this.
        pass

    # Reads are pairs (length, index?)
    rids['CyclesAsList'] = [ (ri_xml.read_and_length[i], ri_xml.read_and_indexed[i] == 'Y')
                             for i in
                             sorted(ri_xml.read_and_length.keys(), key=int) ]

    #Which file is actually providing the SampleSheet?
    try:
        rids['SampleSheet'] = os.path.basename(os.readlink(run_dir + "/SampleSheet.csv"))
    except OSError:
        # Weird - maybe not a link?
        rids['SampleSheet'] = "SampleSheet.csv"
    try:
        ss_csv = SampleSheetReader(run_dir + "/SampleSheet.csv")
    except Exception:
        # We can live without this if the sample sheet is invalid
        ss_csv = None

    #When is this  report being made?
    rids['ReportDateTime'] = fmt_time()

    #Slice the sample sheet by lane
    rids['Lanes'] = []
    rids['ProjectInfo'] = {}

    if ss_csv:
        # Snag the 'real' experiment name
        rids['ExperimentSS'] = ss_csv.headers.get('Experiment Name')

        #Translate all the project numbers to names in one go
        #If you try to feed this script an old 2500 Sample Sheet this is where it will fail.
        assert 'sampleproject' not in ss_csv.column_mapping, \
            "A sampleproject (without the underscore) column was found. Is this an old 2500 SampleSheet?"
        rids['ProjectInfo'] = project_real_name(
                                set([ line[ss_csv.column_mapping['sample_project']]
                                      for line in ss_csv.samplesheet_data ]),
                                project_name_list )

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

        # I used to set 'NoPool' to '' at this point but it turned out to be a bad idea.

        #Avoid use of defaultdict as it gums up YAML serialization. This is equivalent.
        res.setdefault(sample_project, dict()).setdefault(sample_pool, []).append(sample_lib)

    return res

def output_txt(rids, fh):
    def p(*a): print(*a, file=fh)

    # Show the pipeline version
    p( "Illuminatus {} [{}@{}:{}]".format(
                    os.environ.get("ILLUMINATUS_VERSION", "[unknown version]"),
                        os.environ.get("USER", "[unknown user]"),
                           os.environ.get("HOSTNAME", "[unknown host]"),
                              os.path.abspath(os.path.dirname(__file__)) ) )
    p( "" )

    # Basic metadata, followed be a per-lane summary.
    expname_from_xml = rids.get('ExperimentName') or 'unknown'
    expname_from_ss  = rids.get('ExperimentSS')

    p( f"Run ID: {rids['RunId']}" )
    if expname_from_ss and expname_from_ss != expname_from_xml:
        # We have conflicting names for this experiment
        p( f"Experiment: {expname_from_xml} ({expname_from_ss})" )
    else:
        # We have one experiment name
        p( f"Experiment: {expname_from_xml}" )

    p( f"Instrument: {rids['Instrument']}" )
    p( f"Flowcell Type: {rids.get('FCType', 'unknown')}" )  # May be missing if the YAML file is old.
    p( f"Read length: {rids['Cycles']}" )
    p( f"Active SampleSheet: SampleSheet.csv -> {rids['SampleSheet']}" )
    p( "" )

    p( f"Samplesheet report at {rids['ReportDateTime']}:" )

    # Summarize each lane
    prn = rids['ProjectInfo']
    for lane in rids['Lanes']:
        p( f"Lane {lane['LaneNumber']}:" )

        for project, pools in sorted(lane['Contents'].items()):
            # pools will be a dict of poolname : [ library, ... ]

            # Special case for PhiX
            if project == 'ControlLane' and any(pools == {np: ['PhiX']} for np in NON_POOLS):
                p( "    - PhiX")

            else:

                contents_str = ' '.join(squish_project_content(pools))

                contents_label = 'Libraries' if set(pools).issubset(NON_POOLS) else \
                                 'Contents' if not set(pools).isdisjoint(NON_POOLS) else \
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
    def p(*a): print('\t'.join(a), file=fh)

    #Headers
    p("Lane", "Project", "Pool/Library", "Loaded (pmol)", "Loaded PhiX (%)")

    for lane in rids['Lanes']:

        #This time, squish content for all projects together when listing the pools.
        #If there are more than 5 things in the lane, abbreviate the list. Users can always look
        #at the detailed table.
        pools_union = dict_union(lane['Contents'].values())
        contents_str = ','.join( squish_project_content( pools_union , 5) )

        p( lane['LaneNumber'],
           ','.join( sorted(lane['Contents']) ),
           contents_str,
           lane['Loading'].get('pmol', 'unknown'),
           lane['Loading'].get('phix', 'unknown') )

def dict_union(list_of_dicts):
    """Given a list of dicts, combine them together.
       If two dicts have a common key, sum the values.
    """
    # I tried the funky looking one-liner comprehension:
    # {k: v for d in list_of_dicts for k, v in d.items()}
    # But that just takes the last value if there is a clash
    res = dict()
    for d in list_of_dicts:
        for k, v in d.items():
            if k in res:
                res[k] += v
            else:
                res[k] = v
    return res

def squish_project_content(dict_of_pools, maxlen=0):
    """Given a dict taken from rids['Lanes'][n]['Contents'] -- ie. a dict of pool: content_list
       returns a human-readable list of contents.
    """
    all_pools = sorted([ p for p in dict_of_pools if p not in NON_POOLS ])
    non_pooled_libs = sorted([ p for np in NON_POOLS for p in dict_of_pools.get(np,[]) ])

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

def get_chemistry(run_params, instrument):
    """Get the 'Consumable Version' from params and interpret it.
       At present this tells us if the NovaSeq chemistry is 1.0 or 1.5
    """
    con_vers = run_params.get('Consumable Version')

    if not con_vers:
        return None

    con_note = "unknown"
    if instrument.startswith('novaseq_'):
        if con_vers == '1':
            con_note = "chemistry 1.0"
        elif con_vers == '3':
            con_note = "chemistry 1.5; revcomp index2"

    return f"SCV{con_vers} ({con_note})"

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
        # Go to RT. The current query mode hits the database as configured
        # by ~/.rt_settings and looks for tickets in the eg-projects queue.
        try:
            from illuminatus.RTQuery import get_project_names

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
