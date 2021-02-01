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

from interop import py_interop_run_metrics, py_interop_run, py_interop_summary
from interop.py_interop_metrics import index_out_of_bounds_exception

def get_numbers_from_rundir(run_dir):
    """Returns a data structure with all the numbers I need
    """
    res = dict()

    # Depending on the type of flowcell we might have types or %s
    res['type'] = '%'

    # The "Tile Metrics" and "Extended Tile Metrics" seem to be needed
    metrics_handle = get_run_metrics_handle(run_dir)
    tms = metrics_handle.tile_metric_set()
    etms = metrics_handle.extended_tile_metric_set()

    # Now go lane by lane. This gets a tuple eg. (1, 2)
    res['lanes'] = list(tms.lanes())

    for alane in res['lanes']:
        # Add to the overall dict
        laneres = res['Lane {}'.format(alane)] = dict(lane=alane)

        # Now go tile by tile and get the raw numbers
        import pdb; pdb.set_trace()


    import pdb ; pdb.set_trace()

    metrics_handle.total_summary()

def get_run_metrics_handle(run_dir):
    """ Load the goodies from the .bin files in the InterOp directory.
        This black magic is copy-pasted straight out of the tutorial linked above!
    """
    #print("Examining: {}".format(run_dir))

    valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
    py_interop_run_metrics.list_summary_metrics_to_load(valid_to_load)
    run_metrics = py_interop_run_metrics.run_metrics()
    run_metrics.read(run_dir, valid_to_load)

    return run_metrics

    """
    # No summary needed here we're going tile by tile.
    summary = py_interop_summary.run_summary()
    py_interop_summary.summarize_run_metrics(run_metrics, summary)

    return summary
    """

def main(run_dir):

    # For now just get the info and dump as YAML
    res = get_numbers_from_rundir(run_dir)

    print(yaml.safe_dump(res), end='')

if __name__ == '__main__':
    main(*sys.argv[1:])
