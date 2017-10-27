#!/usr/bin/env python3

# This script takes the InterOp files
# and summarizes the yield and error rate per lane and overall.

# To make my life simpler, I'll use the Python bindings to read the InterOp
# files directly. (Try 'python -m interop --test' to see if the install is good)

# The tutorial at https://github.com/Illumina/interop/blob/master/docs/src/Tutorial_01_Intro.ipynb
# is very pertinent.

import os, sys
from pprint import pprint
from math import isnan
import yaml

from interop import py_interop_run_metrics, py_interop_run, py_interop_summary
from interop.py_interop_metrics import index_out_of_bounds_exception

def main(run_dir, out_dir=None):
    """Get the info from run_dir. If out_dir is set, dump individual
       files into all the laneN subdirectories. Else dump the info as
       raw YAML to stdout.
    """
    if os.path.isfile(run_dir):
        #Load from pre-made YAML
        with open(run_dir) as yfh:
            res = yaml.safe_load(yfh)
    else:
        #Actually gather the metadata
        summary = get_run_metrics_handle(run_dir)

        res = extract_info(summary)
        res['run_dir'] = run_dir.rstrip('/')

    # Dump to YAML
    print(yaml.safe_dump(res, default_flow_style=False), end='')

def get_run_metrics_handle(run_dir):
    """ Load the goodies from the .bin files in the InterOp directory.
        This black magic is copy-pasted straight out of the tutorial linked above!
    """
    #print("Examining: {}".format(run_dir))

    valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
    py_interop_run_metrics.list_summary_metrics_to_load(valid_to_load)
    run_metrics = py_interop_run_metrics.run_metrics()
    run_metrics.read(run_dir, valid_to_load)
    summary = py_interop_summary.run_summary()
    py_interop_summary.summarize_run_metrics(run_metrics, summary)

    return summary

def extract_info(summary):
    """ Now we can extract the info per read into a data structure
        suitable for saving as YAML.
    """
    overview = dict()
    res = dict(overview=overview)

    def f(val):
        """See format_value in the example code.
           We don't want nans in our output so zero them (I think??)
        """
        try: val = val()
        except TypeError: pass
        try: val = val.mean()
        except AttributeError: pass
        return None if isnan(val) else val

    def get_dict(summ_part, **extra):
        if summ_part:
            return dict(
                    yield_g           = f(summ_part.yield_g),
                    projected_yield_g = f(summ_part.projected_yield_g),
                    error_rate        = f(summ_part.error_rate),
                    percent_gt_q30    = f(summ_part.percent_gt_q30),
                    cycles            = 0,
                    **extra )
        else:
            return dict(
                    yield_g           = 0.0,
                    projected_yield_g = 0.0,
                    error_rate        = 0.0,
                    percent_gt_q30    = 0.0,
                    cycles            = 0,
                    **extra )

    # Get the totals
    overview['Totals'] = get_dict(summary.total_summary())
    overview['Non-Index Totals'] = get_dict(summary.nonindex_summary())

    # Actually the total error rate should really be None since we don't hav error rates
    # for index reads. The Illumina code just copies the vlaue from the non-indexed total
    # anyway.
    overview['Totals']['error_rate'] = None

    try:
        # Get the overview
        for i in range(20):
            rinfo = overview[str(summary.at(i).read().number())] = get_dict(summary.at(i).summary())

            rinfo['is_index'] = summary.at(i).read().is_index()
            rinfo['cycles']   = summary.at(i).read().total_cycles()

            # Add the cycles to the overall info
            overview['Totals']['cycles'] += rinfo['cycles']
            if not rinfo['is_index']:
                overview['Non-Index Totals']['cycles'] += rinfo['cycles']

        assert False, "We shouldn't get here"
    except index_out_of_bounds_exception:
        #No more reads to process. No worries.
        pass

    # Now for the per-lane stats. Very similar. But this time I have to tot up all the
    # totals manually for some reason.
    try:
        for lane in range(20):
            mylaneinfo = dict()
            res['lane{}'.format(summary.at(0).at(lane).lane())] = mylaneinfo

            mylaneinfo['Totals']           = get_dict(None, _q30=[0,0], _e=[0,0])
            mylaneinfo['Non-Index Totals'] = get_dict(None, _q30=[0,0], _e=[0,0])

            try:
                for i in range(20):
                    #foo = summary.at(i).read()
                    #import pdb; pdb.set_trace()

                    # Need to test on a multi-lane run. Obviously on the MiSeq these numbers
                    # come out the same.
                    rinfo = mylaneinfo[str(summary.at(i).read().number())] = get_dict(summary.at(i).at(lane))

                    # Exactly the same as added to overview
                    rinfo['is_index'] = summary.at(i).read().is_index()
                    rinfo['cycles']   = summary.at(i).read().total_cycles()

                    # Add the info to the appropriate totals. This time the code doesn't do the
                    # calculations for me.
                    for tbit in [mylaneinfo['Totals']] if rinfo['is_index'] \
                        else [mylaneinfo['Totals'], mylaneinfo['Non-Index Totals']]:

                            tbit['cycles'] += rinfo['cycles']
                            tbit['yield_g'] += rinfo['yield_g']
                            tbit['projected_yield_g'] += rinfo['projected_yield_g']

                            # percent_gt_q30 needs to be a weighted mean by summary.at(i).read().useable_cycles()
                            # so we need to tot these up as well as doing the calculation
                            tbit['_q30'][0] += summary.at(i).at(lane).percent_gt_q30()  * summary.at(i).read().useable_cycles()
                            tbit['_q30'][1] += summary.at(i).read().useable_cycles()
                            tbit['percent_gt_q30'] = f(tbit['_q30'][0] / tbit['_q30'][1])

                            # same for error_rate, as far as I can see
                            tbit['_e'][0] += summary.at(i).at(lane).error_rate().mean() * summary.at(i).read().useable_cycles()
                            tbit['_e'][1] += summary.at(i).read().useable_cycles()
                            tbit['error_rate'] = f(tbit['_e'][0] / tbit['_e'][1])

                assert False, "We shouldn't get here - 20 reads"
            except index_out_of_bounds_exception:
                pass

            # Having processed all reads for this lane, scrub _q30 and _e
            for rinfo in mylaneinfo.values():
                for k in list(rinfo):
                    if k.startswith('_'): del rinfo[k]

        assert False, "We shouldn't get here - 20 lanes"
    except index_out_of_bounds_exception:
        #Out of lanes.
        pass

    return res

if __name__ == "__main__":
    main(*sys.argv[1:])
