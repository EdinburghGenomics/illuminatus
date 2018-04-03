#!/usr/bin/env python3
import sys, os
import datetime
import yaml, json
from argparse import ArgumentParser
from itertools import chain

""" This script builds the Project Summary table on the overview pages.
    See also summarize_lane_contents.py and summarize_yield.py

    It needs to get info from the following places:
        all Stats.json (I could have stats_json_aggregator.py read the extra info but
                        it seems better to have this script read the stats directly)
        pipeline/sample_summary.yml (Because this knows what the projects are called!)

    Output will be in tsv or mqc format following the patter in summarize_lane_contents.py
"""

def parse_args():
    description = """This script is part of the Illuminatus pipeline.
It makes a fragments-per-project-per-lane matrix for a run.
Output may be in MQC or TSV format or raw YAML. MQC is suitable for MultiQC custom
content - http://multiqc.info/docs/#custom-content, while TSV/YAML is handy
for debugging.
"""

# Note there is also RunMetaData.py and RunStatus.py which do similar jobs but this should
# be the only script that is querying the LIMS and looking at the details of the SampleSheet
# lines.

    a = ArgumentParser(description=description)
    a.add_argument("--project_name_list",
                   help="Supply a comma-separated list of project names." +
                        " Normally they would be obtained from sample_summary.yml." +
                        " You can equivalently setenv PROJECT_NAME_LIST." )
    a.add_argument("--sample_summary",
                   help="Read project names from the supplied sample_summary.yml")
    a.add_argument("--from_yml",
                   help="Get the info from the supplied YAML file, not by" +
                        " scanning the directory and the LIMS." )
    a.add_argument("--yml",
                   help="Output in YAML format to the specified file (- for stdout)." )
    a.add_argument("--mqc",
                   help="Output for MultiQC to the specified file (- for stdout)." )
    a.add_argument("--tsv",
                   help="Output in TSV format to the specified file (- for stdout)." )

    parser.add_argument("json", type=str, nargs='+',
                        help="Stats to be digested.")

    return a.parse_args()

def main(args):

    # First order of business is to digest all the Stats.json files
    # This gives me a dict {(sample_id, lane) -> fragments}
    # but I can't directly aggregate these by project until I have the sample_summary.yml
    all_stats_from_json = extract_stats_from_json(args.json)

    # A dummy sample summary
    sample_summary = { 'ProjectInfo': dict(), 'Lanes', list() }
    if args.sample_summary:
        with open(args.sample_summary) as yfh:
            sample_summary = yaml.safe_load(yfh)

    # A list of names
    project_name_list = (args.project_name_list or os.environ.get('PROJECT_NAME_LIST', '')).split(',')

    # Now a mapping of project_number->name, combining both. The name list takes precedence.
    # Note that info in the .yml looks like this:
    #    ProjectInfo:
    #      '11200':
    #         name: 11200_Hickey_John
    #         url: https://www.wiki.ed.ac.uk/display/GenePool/11200_Hickey_John
    project_to_name = { k: v.get('name', k) for k, v in sample_summary['ProjectInfo'].items() }
    project_to_name.update( [pn.split('_', 1) for pn in project_name_list if '_' in pn] )

    # Resolve the samples down to projects with the mapping in sample_summary, or else
    # by guessing (samples generally start with the project number!).
    # This gets us from {lane -> {pool_library -> fragments}} to {(project, lane) -> fragments}
    all_stats_by_project = aggregate_by_project(all_stats_from_json, sample_summary['Lanes'])

    #See where we want to put it (loop nicked from summarize_lane_contents)
    for dest, formatter in [ ( args.yml, output_yml ),
                             ( args.mqc, output_mqc ),
                             ( args.tsv, output_tsv ) ]:
        if dest:
            if dest == '-':
                formatter(all_stats_by_project, project_to_name, sys.stdout)
            else:
                with open(dest, 'w') as ofh:
                    formatter(all_stats_by_project, project_to_name, ofh)

def aggregate_by_project(all_stats_by_pool, lanes_summary):
    """ Gets us from {lane -> {pool_library -> fragments}} to {(project, lane) -> fragments}
        by using the info in lanes_summary or failing that inferring the project name from
        the pool name (should be the first 5 characters)
    """
    res = dict()

    # Work one lane at a time, driven by the keys in all_stats_by_pool
    for lane, reads_by_sample in all_stats_by_pool.items():
        # Get the corresponding info from sample_summary.yml
        lane_contents = [ l['Contents'] for l in lanes_summary if l['LaneNumber'] == lane ]
        # lane_contents is now a list of (hopefully exactly one) dicts.
        # Now take a deep breath and let's unpack it to get a lookup table!
        sample_to_project = { "{}__{}".format(pool, lib): proj
                              for lc in lane_contents
                              for proj, pool_dict in lc.items()
                              for pool, lib_list in pool_dict.items()
                              for lib in lib_list }

        # Now translate and sum
        for sample, fragments in reads_by_sample.items():

            project = sample_to_project.get(sample, sample[0:5])
            res[(project, lane)] = fragments + res.get((project, lane), 0)

    return res


def output_yml(all_stats_by_project, project_to_name, fh):
    """ Super-simple YAML dumper.
    """
    struct = dict( reads_by_project = all_stats_by_project,
                   project_to_name = project_to_name )
    print(yaml.safe_dump(struct, default_flow_style=False), file=fh, end='')

def output_tsv(all_stats_by_project, project_to_name, fh):
    """ Output as TSV.
        Projects in rows, lanes in columns.
    """
    # We could have projects in project_to_name that are not in the Stats
    # and vice versa. Include them all and sort by ID.
    projects = sorted(set( k[0] for k in chain(
                                    all_stats_by_project.keys(),
                                    project_to_name.items() ))
    lanes = sorted(set( k[1] for k in all_stats_by_project.keys() ))

    # Header:
    print('\t'.join(['Project'] + ['Lane {}'.format(n) for n in lanes] + ['Total']), file=fh)

    # One row per project
    p_by_l_totals = [ 0 for l in lanes ] + [0]
    for p in projects:
        # Get the vlaues for the row and tack on the sum
        p_by_l = [ all_stats_by_project.get((p,l), 0) for l in lanes ]
        p_by_l.append(sum(p_by_l))

        row = [project_to_name.get(p, p)] + p_by_l
        print('\t'.join(row), file=fh)

        # Add the row to the running sum - NumPy would do this more neatly.
        p_by_l_totals = [sum(x) for x in zip(p_by_l_totals, p_by_l)]

    # And anow print the row of totals at the bottom
    last_row = [ 'Total' ] + p_by_l_totals


def exract_stats_from_json(json_files):
    """ Go through all the JSON files and make a dict { lane -> { pool_library -> fragments} }
        Somewhat similar to stats_json_aggregator.py.
    """
    all_stats = dict()

    for stats_file in args.json:
        with open(stats_file) as fh: stats_json = json.load(fh)

        # Add the conversion stats per lane
        for cr_per_lane in stats_json['ConversionResults']:
            ln = str(cr_per_lane["LaneNumber"])
            assert ln not in all_stats, "Lane {} seen already.".format(ln)

            all_stats[ln] = { r["SampleId"]: r["NumberReads"] for r in cr_per_lane["DemuxResults"] }

    return all_stats

if __name__=="__main__":
    main(parse_args())
