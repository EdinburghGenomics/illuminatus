#!/usr/bin/env python3

# This script reads InterOp for a run and generates GNUPlot
# instructions to make a plot of %Occupied vs. %Pass Filter,
# as requested by Matt.

# To make my life simpler, I'll use the Python bindings to read the InterOp
# files directly. (This is now a standard PyPi module - try
# 'python3 -m interop --test' to see if the install is good)

# The tutorial at https://github.com/Illumina/interop/blob/master/docs/src/Tutorial_01_Intro.ipynb
# is very pertinent.

import os, sys
import yaml
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from interop import py_interop_run_metrics, py_interop_run
from interop.py_interop_metrics import index_out_of_bounds_exception

# This needs to be an integer- see comment below
DEF_MAX_DENSITY = 1000

def get_numbers_from_rundir(run_dir):
    """Returns a data structure with all the numbers I need
    """
    res = dict()

    # Depending on the type of flowcell we might have #s or %s
    res['type'] = '?'

    # The "Tile Metrics" and "Extended Tile Metrics" seem to be needed
    metrics_handle = get_run_metrics_handle(run_dir)
    tms = metrics_handle.tile_metric_set()
    etms = metrics_handle.extended_tile_metric_set()

    # Now go lane by lane. This gets a tuple eg. (1, 2)
    res['lanes'] = list(tms.lanes())

    for alane in res['lanes']:
        # Add to the overall dict
        laneres = res['Lane {}'.format(alane)] = list()

        # Now go tile by tile and get the raw numbers
        tiles_on_lane = tms.tile_numbers_for_lane(alane)

        for atile in tiles_on_lane:
            cluster_count = int(tms.get_metric(alane, atile).cluster_count())
            clusters_pf = int(tms.get_metric(alane, atile).cluster_count_pf())

            try:
                # If this works we're on a patterned flowcell
                clusters_occup = int(etms.get_metric(alane, atile).cluster_count_occupied())

                pct_occup = etms.get_metric(alane, atile).percent_occupied()
                pct_pf = tms.get_metric(alane, atile).percent_pf()

                laneres.append( dict( tile = atile,
                                      count = cluster_count,
                                      occ = clusters_occup,
                                      pf = clusters_pf,
                                      pct_occup = pct_occup,
                                      pct_pf = pct_pf) )

                assert res['type'] != '#'
                res['type'] = '%'

            except index_out_of_bounds_exception:
                # OK so we're on a MiSeq flowcell
                cluster_density_k = tms.get_metric(alane, atile).cluster_density_k()
                cluster_density_pf_k = tms.get_metric(alane, atile).cluster_density_pf_k()

                laneres.append( dict( tile = atile,
                                      count = cluster_count,
                                      pf = clusters_pf,
                                      density_k = cluster_density_k,
                                      pf_density_k = cluster_density_pf_k ) )

                assert res['type'] != '%'
                res['type'] = '#'

        # OK can we do something cunning with the cluster density to get some reasonable axis sizes
        # for the MiSeq plots? Hmmm.
        # Just eyeballing the numbers, I think having a plot where the max density is 1000k or maybe 900k
        # makes sense.

    return res

def get_run_metrics_handle(run_dir):
    """ Load the goodies from the .bin files in the InterOp directory.
        This black magic is copy-pasted straight out of the tutorial linked above!
    """
    #print("Examining: {}".format(run_dir))

    valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
    for v2l in (py_interop_run.Tile, py_interop_run.ExtendedTile):
        valid_to_load[v2l] = 1

    run_metrics = py_interop_run_metrics.run_metrics()
    run_metrics.read(run_dir, valid_to_load)

    return run_metrics

def format_gnuplot(res):
    return ['line1', 'line2', '#type={}'.format(res['type']),
            'set xrange [0:{}]'.format(res['density_max'])]

def main(args):

    if args.from_yaml:
        with open(args.from_yaml) as yfh:
            res = yaml.safe_load(yfh)
    else:
        res = get_numbers_from_rundir(args.run_dir)

    # The density max range may be saved within the YAML but the command line option
    # always takes precedence. Note we can tell if --density_max was specified on the
    # command line because the arg will always be a float, whereas the default is an
    # int. Yes this is a hack.
    if res['type'] == '#':
        if type(args.density_max) is float:
            res['density_max'] = args.density_max
        elif not res.get('density_max'):
            res['density_max'] = float(args.density_max)

    if args.dump_yaml:
        print(yaml.safe_dump(res), end='')
    else:
        print(*format_gnuplot(res), sep='\n')

def parse_args(*argv):
    """Usual ArgumentParser
    """
    desc = "Get tile density metrics from InterOp and format for GNUPlot"

    parser = ArgumentParser( description = desc,
                             formatter_class = ArgumentDefaultsHelpFormatter )

    parser.add_argument("run_dir", type=str, nargs='?', help="Run to be examined.")
    parser.add_argument("--dump_yaml", action="store_true", help="Output YAML not GNUPlot commands.")
    parser.add_argument("--from_yaml", help="Load from YAML not from run dir.")
    parser.add_argument("--density_max", type=float, help="Override axis limits when plotting density.",
                                         default=DEF_MAX_DENSITY)

    args = parser.parse_args(*argv)

    if args.from_yaml and args.run_dir:
        sys.exit("Inspecting a run directly and loading from YAML are mutually exclusive.")

    return args

if __name__ == '__main__':
    main(parse_args())
