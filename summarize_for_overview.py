#!/usr/bin/env python3
import os, sys
from collections import defaultdict, OrderedDict
from datetime import datetime

import yaml, yamlloader
from urllib.parse import quote as url_quote

from illuminatus import illuminatus_version

"""This script provides information about a sequencing run that appears at the top
   of each MultiQC report page.
   Most of the info comes from pipeline/sample_summary.yml that is created by
   summarize_lane_contents.py (as run by driver.sh).
   In addition it will look at:
     RTAComplete.txt (timestamp only)
     SampleSheet.csv (to generate full path based on current directory)
     start_times file in pipeline folder
"""

def get_pipeline_info(run_path):
    """If the pipeline started actually demultiplexing we can get some extra bits of info
       The pipeline/start_times file contains the start time, as well as the version, and extra lines are
       added on each redo. It's written out directly by driver.sh just before it first triggers this script
       (to update the report prior to running Snakefile.demux)
    """
    pipeline_info = dict()
    try:
        with open(os.path.join( run_path , 'pipeline', 'start_times')) as stfh:
            last_line = list(stfh)[-1].rstrip('\n')

    except FileNotFoundError:
        #OK, the pipeline didn't start
        return None

    if '@' in last_line:
        pipeline_info['version'], pipeline_info['start'] = last_line.split('@', 1)
    else:
        #If the version wasn't logged, this must have been 0.0.2 (or earlier)
        pipeline_info['version'], pipeline_info['start'] = '0.0.?', last_line

    # Now if this script belongs to a different version we need to say so, and we
    # end up with a version like 0.0.3+0.1.0, ie. demultiplexed with one version and
    # QC'd with another. This may well be fine, but redo the run from scratch if you need to
    # ensure consistency.
    if illuminatus_version != pipeline_info['version']:
        pipeline_info['version'] += "+" + illuminatus_version

    # If the pipeline started, the sequencer MUST have finished.
    touch_file = os.path.join( run_path , 'RTAComplete.txt' )
    pipeline_info['finish'] = datetime.fromtimestamp(os.stat(touch_file).st_mtime).ctime()

    return pipeline_info

def wrangle_experiment_name(rids):
    """Returns a 2-item list [label, link] for the Experiment Name, or just a name
       if there is no link to make.
    """
    expname_from_xml = rids.get('ExperimentName')
    expname_from_ss  = rids.get('ExperimentSS')

    if not expname_from_xml:
        # No linky??
        if expname_from_ss:
            # consistent with summarize_lane_contents.py
            return expname_from_ss or 'unknown ({})'.format(expname_from_ss)
        else:
            return 'unknown'

    else:
        # Hyperlink the expt name to BaseSpace. We can't do this directly since there is an unpredictable
        # number in the URL but this will do. This always uses the expname_from_xml value.
        linky = "https://basespace.illumina.com/search/?type=run&query=" + url_quote(expname_from_xml)

        if expname_from_ss and expname_from_ss != expname_from_xml:
            # Name conflict
            return [ "[{}] ({})".format(expname_from_xml, expname_from_ss), linky ]
        else:
            # All consistent, or expname_from_ss is just missing
            return [ expname_from_xml, linky ]


def get_idict(rids, run_path, pipeline_info=None):
    """Reformat the rids data into what we want for the overview, adding a few extra
       bits.
    """
    # Note that we can sometimes get the flowcell type from the params (NovaSeq) and
    # otherwise from the info (everything else).

    idict = dict()

    # Funny business with the experiment name - we have a 2-item list of [name, link]
    expname = wrangle_experiment_name(rids)

    ss_path = os.path.join( run_path , 'SampleSheet.csv' )
    sample_sheet = [ os.path.basename(os.path.realpath( ss_path )),
                     os.path.realpath( ss_path ) ]

    idict['pre_start_info'] = OrderedDict([
            ('Run Date', rids['RunDate']),
            ('Run ID', rids['RunId']),
            ('Experiment', expname),
            ('Instrument', rids['Instrument']),
            ('Flowcell Type', rids.get('FCType') or 'unknown'),
            ('Chemistry', rids.get('Chemistry')), # May be None
            ('LaneCount', int(rids['LaneCount'])), # MultiQC treats this specially
            ('Cycles', rids['Cycles']), # '251 [12] 251',
            ('Pipeline Script', get_pipeline_script()),
            ('Sample Sheet', sample_sheet), # [ name, path ]
            ('t1//Run Start', rids.get('RunStartTime') or rids['RunDate']),
        ])

    # Eliminate empty value.
    if not idict['pre_start_info']['Chemistry']:
        del idict['pre_start_info']['Chemistry']

    if pipeline_info:
        idict['post_start_info'] = {
            'Pipeline Version': pipeline_info['version'],
            't3//Pipeline Start': pipeline_info['start'],
            't2//Sequencer Finish': pipeline_info['finish']
        }

    return idict

def get_pipeline_script():
    """Presumably this. Note we also report the pipeline version(s) in post_start_info
    """
    return os.path.realpath(os.path.dirname(__file__)) + '/driver.sh'

def main(run_folder='.'):

    # Most of what we care about is in pipeline/sample_summary.yml, which is unordered.
    # rids == Run Info Data Structure
    with open(os.path.join(run_folder, 'pipeline', 'sample_summary.yml')) as rfh:
        rids = yaml.safe_load(rfh)

    # If the pipeline has actually run (demultiplexed) there will be some info about that
    pipeline_info = get_pipeline_info(run_folder)

    # We format everything into an OrderedDict
    idict = get_idict(rids, run_folder, pipeline_info)

    # And print it
    print( yaml.dump( idict,
                      Dumper = yamlloader.ordereddict.CSafeDumper,
                      default_flow_style = False ), end='' )

if __name__ == '__main__':
    #If no run specified, examine the CWD.
    main(*sys.argv[1:])
