#!/usr/bin/env python3
import sys, os
import json
from argparse import ArgumentParser
from statistics import mean, stdev

from illuminatus.YAMLOrdered import yaml
from illuminatus.Formatters import rat

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

    # I want to be able to output multiple MQC files in one go...
    for metric in "frag lib bal".split():
        for pool in "pool proj".split():
            a.add_argument("--mqc_{}_{}".format(metric, pool),
                           help="Output specific stats for MultiQC to a file")

    a.add_argument("--metric",
                   help="Output Fragments, Libraries, or Balance (ignored for --yml output)")
    a.add_argument("--by_pool", action="store_true",
                   help="Collate by pool rather than by project (ignored for --yml output)")
    a.add_argument("--print_even_if_empty",
                   help="Disable the sanity check that stops us producing useless MQC tables.")

    a.add_argument("json", type=str, nargs='+',
                   help="Stats to be digested.")

    return a.parse_args()

def main(args):

    # First order of business is to digest all the Stats.json files
    # This gives me a dict {(sample_id, lane) -> fragments}
    # but I can't robustly aggregate these by project until I have the sample_summary.yml
    all_stats_from_json = extract_stats_from_json(args.json)

    # A dummy sample summary, then try to load the real one.
    sample_summary = { 'ProjectInfo': dict(), 'Lanes': list() }
    if args.sample_summary:
        with open(args.sample_summary) as yfh:
            sample_summary = yaml.safe_load(yfh)

    # A list of names can be provided on the command line...
    project_name_list = (args.project_name_list or os.environ.get('PROJECT_NAME_LIST', '')).split(',')

    # Now a mapping of project_number->name, combining both. The name list takes precedence.
    # Note that info in the .yml looks like this:
    #    ProjectInfo:
    #      '11200':
    #         name: 11200_Hickey_John
    #         url: https://www.wiki.ed.ac.uk/display/GenePool/11200_Hickey_John
    project_to_name = { k: v.get('name', k) for k, v in sample_summary['ProjectInfo'].items() }
    project_to_name.update( [(pn.split('_')[0], pn) for pn in project_name_list if '_' in pn] )

    # Resolve the samples down to projects with the mapping in sample_summary, or else
    # by guessing (samples generally start with the project number!).
    # This gets us from {lane -> {pool_library -> fragments}} to {(lane/project) -> fragments}
    all_stats_by_project = aggregate_by_project(all_stats_from_json, sample_summary['Lanes'])
    all_stats_by_pool = aggregate_by_pool(all_stats_from_json)

    # At this point it's also useful to be able to explicitly get the pools by project
    pools_per_project = get_pools_per_project(project_to_name.keys(), sample_summary['Lanes'])

    #See where we want to put it (loop nicked from summarize_lane_contents)
    for dest, formatter in [ ( args.yml, output_yml ),
                             ( args.mqc, output_mqc ),
                             ( args.tsv, output_tsv ) ]:
        if dest:
            if dest == '-':
                formatter(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, sys.stdout)
            else:
                with open(dest, 'w') as ofh:
                    formatter(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, ofh)

    #Also allow multiple MQC outputs
    for metric in "frag lib bal".split():
        for pool in "pool proj".split():
            dest = vars(args)["mqc_{}_{}".format(metric, pool)]

            # Manipulate args because I'm lazy
            args.by_pool = (pool == "pool")
            args.metric = dict(frag='Fragments', lib='Libraries', bal="Balance")[metric]

            if dest == '-':
                output_mqc(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, sys.stdout)
            elif dest:
                with open(dest, 'w') as ofh:
                    output_mqc(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, ofh)

def cov(counts_list):
    """ Standard CoV (barcode balance) calculation
    """
    return rat( stdev(counts_list), mean(counts_list) )

def get_pools_per_project(project_list, lanes_summary):
    """ Tots up the pools for each project. When calculating barcode balance by pool
        there may be a "NoPool" which has samples from multiple projects, so I can't reliably
        infer this info later. This works it out explicitly.
        Note that if a pool is loaded on multiple lanes it will appear multiple times.
    """
    return { p : [ pool
             for lc in [ l['Contents'] for l in lanes_summary ]
             for proj, pool_dict in lc.items()
             for pool in pool_dict
             if proj == p ]
             for p in project_list }


def aggregate_by_project(all_stats_by_library, lanes_summary):
    """ Gets us from {lane -> {pool_library -> fragments}} to three dicts
        of {(lane/project) -> value} by using the info in lanes_summary.
    """
    # This will map {(lane/project) -> [list of counts]}
    counts_by_lane_proj = dict()
    counts_by_lane = dict()
    counts_by_proj = dict()

    # Work one lane at a time, driven by the keys in all_stats_by_library
    for lane, reads_by_library in all_stats_by_library.items():
        # Get the info regarding this lane from sample_summary.yml
        lane_contents = [ l['Contents'] for l in lanes_summary if l['LaneNumber'] == lane ]
        # lane_contents is now a list of (hopefully exactly one!) dicts.
        # Now take a deep breath and let's unpack it to get a lookup table!
        # Of course I'm reconstructing the name from the sample sheet here but I regard the data in the YAML
        # to be already internalised.
        # Since I'm no longer munging pool names ('NoPool' -> '') this mapping should be reliable.
        library_to_project = { "{}__{}".format(pool, lib): proj
                               for lc in lane_contents
                               for proj, pool_dict in lc.items()
                               for pool, lib_list in pool_dict.items()
                               for lib in lib_list }

        # Now translate and sum
        for library, fragments in reads_by_library.items():

            # If the lookup fails, use the first 5 chars of the pool name
            # No, that's dangerous. I'll do this instead...
            project = library_to_project.get(library, 'Unknown')
            counts_by_lane_proj.setdefault('{}/{}'.format(lane, project),[]).append(fragments)
            counts_by_lane.setdefault(lane,[]).append(fragments)
            counts_by_proj.setdefault(project,[]).append(fragments)

    # Now transform those lists to get the three values we want - fragments, libs, balance
    # If there is only one library the balance should be absent but where there are several library
    # and no reads it will be .nan
    # Add the balance for the whole lane and for the project over all lanes.
    # as we can't calculate this from the aggregate figures.
    res = dict( Fragments = {k: sum(v) for k, v in counts_by_lane_proj.items()},
                Libraries = {k: len(v) for k, v in counts_by_lane_proj.items()},
                Balance   = {k: cov(v) for k, v in counts_by_lane_proj.items() if len(v) > 1},
                LBalance  = {k: cov(v) for k, v in counts_by_lane.items() if len(v) > 1},
                PBalance  = {k: cov(v) for k, v in counts_by_proj.items() if len(v) > 1}  )

    # For completenes poke in an overall barcode balance, though this is likely meaningless
    # when aggregated across projects.
    if sum( len(v) for v in counts_by_lane.values() ) > 1:
        res['LBalance']['All'] = cov([v for l in counts_by_lane.values() for v in l])

    return res

def aggregate_by_pool(all_stats_by_library):
    """ Gets us from {lane -> {pool_library -> fragments}} to three dicts of
        {(lane/project) -> value}. Like aggregate_by_project() but we have no need of
        a library->project mapping in this case.
    """
    # This will map {(lane/project) -> [list of counts]}
    counts_by_lane_pool = dict()
    counts_by_lane = dict()
    counts_by_pool = dict()

    for lane, reads_by_library in all_stats_by_library.items():
        for library, fragments in reads_by_library.items():
            pool = library.split('__', 1)[0]
            counts_by_lane_pool.setdefault('{}/{}'.format(lane, pool),[]).append(fragments)
            counts_by_lane.setdefault(lane,[]).append(fragments)
            counts_by_pool.setdefault(pool,[]).append(fragments)

    # Now transform those lists to get the three values we want - fragments, libs, balance
    # If there is only one library the balance should be absent but where there are several library
    # and no reads it will be .nan
    # Add the balance for the whole lane and for the pool over all lanes.
    # as we can't calculate this from the aggregate figures.
    res = dict( Fragments = {k: sum(v) for k, v in counts_by_lane_pool.items()},
                Libraries = {k: len(v) for k, v in counts_by_lane_pool.items()},
                Balance   = {k: cov(v) for k, v in counts_by_lane_pool.items() if len(v) > 1},
                LBalance  = {k: cov(v) for k, v in counts_by_lane.items() if len(v) > 1},
                PBalance  = {k: cov(v) for k, v in counts_by_pool.items() if len(v) > 1}  )

    # For completenes poke in an overall barcode balance. This might be meaningful with, say
    # the Hickey pools where we'd like a consistent number of reads across all samples.
    if sum( len(v) for v in counts_by_lane.values() ) > 1:
        res['LBalance']['All'] = cov([v for l in counts_by_lane.values() for v in l])

    return res


def output_yml(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, fh):
    """ Super-simple YAML dumper. Ignores args.
    """
    struct = dict( stats_by_pool = all_stats_by_pool,
                   stats_by_project = all_stats_by_project,
                   project_to_name = project_to_name,
                   pools_per_project = pools_per_project )
    print(yaml.safe_dump(struct, default_flow_style=False), file=fh, end='')

def output_mqc(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, fh):
    """This also happens to be YAML but is specifically for display
       in MultiQC. The filename should end in _mqc.yaml (not .yml) in
       order to be picked up.
       I was trying to generate a table with radio buttons that switch views, but
       that doesn't work. Instead I patched MultiQC to put multiple Custom Content
       tables into a section.
    """
    mqc_out = dict(
        id           = 'matrix',
        section_name = 'Project Summary',
        description  = 'Summary of reads and barcode balance broken out by project and pool', # Will only be shown once.
        plot_type    = 'table',
        pconfig      = { 'title': '', 'sortRows': True, 'no_beeswarm': True },
        data         = {},
        headers      = {},
    )

    # Load up the data dict - this bit is copied from output.tsv
    if args.by_pool:
        plabel = 'Pool'
        # The behaviour is that if args.metric is invalid we get a failure here
        all_stats = all_stats_by_pool
        stats_for_metric = all_stats[args.metric]
        p_to_name = dict()
    else:
        plabel = 'Project'
        all_stats = all_stats_by_project
        stats_for_metric = all_stats[args.metric]
        p_to_name = project_to_name

    if args.metric == 'Fragments':
        mqc_out['id'] += '1_fragments_by' + plabel
        mqc_out['pconfig']['title'] = "Fragments by " + plabel
        agg = sum
        agg_label = 'Total'
        fmt = "{:,}"
    if args.metric == 'Libraries':
        mqc_out['id'] += '2_fragments_by' + plabel
        mqc_out['pconfig']['title'] = "Library Counts by " + plabel
        agg = sum
        agg_label = 'Total'
        fmt = "{:,}"
    if args.metric == 'Balance':
        mqc_out['id'] += '3_fragments_by' + plabel
        mqc_out['pconfig']['title'] = "Barcode Balance by " + plabel
        agg = None
        agg_label = 'Overall'
        fmt = "{:,.03}"

    ps = sorted(set( [k.split('/',1)[1] for k in stats_for_metric] +
                     [k for k in p_to_name] ))
    lanes = sorted(set( [k.split('/',1)[0] for k in stats_for_metric] ))

    for p in ps:
        proj_label = p_to_name.get(p, p)
        mqc_out['data'][proj_label] = { 'lane{}'.format(l): stats_for_metric.get('{}/{}'.format(l,p))
                                        for l in lanes
                                        if '{}/{}'.format(l,p) in stats_for_metric }

        # Add a total if there were >1 lanes
        if len(lanes) > 1:
            if agg:
                p_total = agg(stats_for_metric.get('{}/{}'.format(l,p), 0) for l in lanes)
            else:
                # Must be pre-calculated
                p_total = all_stats['P'+args.metric].get(p, 0)
            mqc_out['data'][proj_label]['total'] = p_total

    # Add a summary row. Since all our projects and pools start with a number or 'N' this should
    # stay at the bottom so long as the title is 'Total' or 'Overall'.
    if agg:
        # Add them up. This time there will be no blanks (maybe zeros)
        l_totals = [ agg(stats_for_metric.get('{}/{}'.format(l,p), 0) for p in ps) for l in lanes ]
        grand_total = agg(l_totals)
    else:
        # Get the pre-calculated values
        l_totals = [ all_stats['L'+args.metric].get(l, 0) for l in lanes ]
        grand_total = all_stats['L'+args.metric].get('All', 0)

    # Only print the summary row if there was more than one project/pool.
    if len(ps) > 1:
        mqc_out['data'][agg_label] = { 'lane{}'.format(l): v for l, v in zip(lanes, l_totals) }
        if len(lanes) > 1:
            mqc_out['data'][agg_label]['total'] = grand_total

    # That's the data loaded. Now to set up the headers.
    mqc_out['pconfig']['col1_header'] = plabel

    for l in lanes:
        mqc_out['headers']['lane{}'.format(l)] = dict( min = 0,
                                                       max = grand_total,
                                                       format = fmt,
                                                       title = "Lane {}".format(l) )
    if len(lanes) > 1:
        mqc_out['headers']['total'] = dict( format = fmt,
                                            title = agg_label )

    # Now decide if we want to skip this. Useless tables are (I think):
    #   Any balance if no lane has more than one sample
    #   Libs/Frags by pool if no project has more than one pool
    #   Balance by project if ditto
    #   Library counts by project if there is only one project
    reason_to_skip = None
    pppv = pools_per_project.values()
    if not args.print_even_if_empty:
        if not stats_for_metric:
            reason_to_skip = "No stats for {}".format(args.metric)

        elif args.by_pool and \
             (args.metric != 'Balance') and \
             not any(len(set(ppp)) > 1 for ppp in pppv):
            reason_to_skip = "No project here has more than one pool, so skipping per-pool summary"

        # In run 180412_M01270_0454_000000000-D3R8F we see that a pool may span multiple projects,
        # so be careful.
        elif not args.by_pool and \
             (args.metric == 'Balance') and \
             not any(len(set(ppp)) > 1 for ppp in pppv) and \
             not sum(len(set(l)) for l in pppv) > len(set(i for l in pppv for i in l)):
            reason_to_skip = "No project here has more than one pool, and no pools span projects, so skipping per-project summary"

        elif (not args.by_pool) and (args.metric == 'Libraries') and not len(pools_per_project) > 1:
            reason_to_skip = "There is only one project"

    if reason_to_skip:
        print("reason_to_skip: '{}'".format(reason_to_skip), file=fh)
        print("data: []", file=fh)
    else:
        # That's all she wrote. Print it out...
        print(yaml.safe_dump(mqc_out, default_flow_style=False), file=fh, end='')


def output_tsv(all_stats_by_pool, all_stats_by_project, project_to_name, pools_per_project, args, fh):
    """ Output as TSV.
        Projects (or pools) in rows, lanes in columns.
    """
    if args.by_pool:
        plabel = 'Pool'
        all_stats = all_stats_by_pool
        p_to_name = dict()
    else:
        plabel = 'Project'
        all_stats = all_stats_by_project
        p_to_name = project_to_name

    # We could have projects in project_to_name that are not in the Stats
    # and vice versa. Include them all and sort by ID.
    ps = sorted(set( [k.split('/',1)[1] for k in all_stats['Libraries']] +
                     [k for k in p_to_name] ))
    lanes = sorted(set( [k.split('/',1)[0] for k in all_stats['Libraries']] ))

    def _str(x):
        if type(x) is float:
            return "{:,.3}".format(x)
        elif type(x) is int:
            return "{:,}".format(x)
        else:
            return str(x)

    for tspec in [ dict(key='Fragments', agg=sum,  agg_label='Total'),
                   dict(key='Libraries', agg=sum,  agg_label='Total'),
                   dict(key='Balance',   agg=None, agg_label='Overall'),
                 ]:

        if args.metric and args.metric != tspec['key']:
            continue

        if not args.metric:
            print("===" + tspec['key'] + "===")

        # Header:
        header = [plabel] + ['Lane{}'.format(n) for n in lanes]
        if len(lanes) > 1:
            header.append(tspec['agg_label'])
        print('\t'.join(header), file=fh)

        # One row per project
        p_by_l_totals = [ 0 for l in lanes ]
        if len(lanes) > 1:
            p_by_l_totals.append(0)

        for p in ps:
            # Get the values for the row and tack on the sum
            p_by_l = [ all_stats[tspec['key']].get('{}/{}'.format(l,p), 0) for l in lanes ]
            if len(lanes) > 1:
                if tspec['agg']:
                    p_by_l.append(tspec['agg'](p_by_l))
                else:
                    # Must be pre-calculated
                    p_by_l.append(all_stats['P'+tspec['key']].get(p, 0))

            row = [p_to_name.get(p, p)] + p_by_l
            print('\t'.join(_str(x) for x in row), file=fh)

            # Add the row to the running sum - NumPy would do this more neatly.
            if tspec['agg']:
                p_by_l_totals = [ tspec['agg'](x) for x in zip(p_by_l_totals, p_by_l) ]

        if not tspec['agg']:
            p_by_l_totals = [ all_stats['L'+tspec['key']].get(l, 0) for l in lanes ]
            if len(p_by_l_totals) > 1:
                p_by_l_totals.append( all_stats['L'+tspec['key']].get('All', 0) )

        # And now print the row of totals at the bottom, if there was >1 project
        if len(ps) > 1:
            last_row = [ tspec['agg_label'] ] + p_by_l_totals
            print('\t'.join(_str(x) for x in last_row), file=fh)


def extract_stats_from_json(json_files):
    """ Go through all the JSON files and make a dict { lane -> { pool_library -> fragments} }
        Somewhat similar to stats_json_aggregator.py.
    """
    all_stats = dict()

    for stats_file in json_files:
        with open(stats_file) as fh: stats_json = json.load(fh)

        # Add the conversion stats per lane
        for cr_per_lane in stats_json['ConversionResults']:
            ln = str(cr_per_lane["LaneNumber"])
            assert ln not in all_stats, "Lane {} seen already.".format(ln)

            all_stats[ln] = { r["SampleId"]: r["NumberReads"] for r in cr_per_lane["DemuxResults"] }

    return all_stats

if __name__=="__main__":
    main(parse_args())
