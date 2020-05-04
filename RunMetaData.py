#!/usr/bin/env python3
import os, sys
from collections import defaultdict
from datetime import datetime

import yaml, yamlloader
from urllib.parse import quote as url_quote

from illuminatus import illuminatus_version
from illuminatus.RunInfoXMLParser import RunInfoXMLParser
from illuminatus.RunParametersXMLParser import RunParametersXMLParser

class RunMetaData:
    """This Class provides information about a sequencing run, given a run folder.
       It is rather similar to RunStatus.py but does not attempt to determine
       the processing status of the run.
       It will parse information from the following sources:
         RunInfo.xml file
         runParameters.xml
         RTAComplete.txt (timestamp only)
         SampleSheet.csv (only for linking - no parsing is attempted)
         start_times file in pipeline folder
    """
    def __init__( self , run_folder , run_path = '' ):

        # here the RunInfo.xml is parsed into an object
        self.run_path_folder = os.path.join( run_path , run_folder )
        try:
            rip = RunInfoXMLParser( self.run_path_folder )
            self.runinfo_xml = rip.run_info
        except Exception:
            #if we can't read it we can't get much info
            #contrast this with RunInfo.py which always returns something.
            raise

        try:
            self.run_params = RunParametersXMLParser( self.run_path_folder ).run_parameters
        except Exception:
            #we can usefully run without this
            self.run_params = defaultdict(lambda: 'unknown')

        # Try to re-jig the date.
        # Note that this is just the timestamp off the runParameters file so if you copy
        # or touch the file it will change.
        try:
            if 'Start Time' in self.run_params:
                self.run_params['Start Time'] = datetime.strptime( self.run_params['Start Time'],
                                                                   '%a %b %d %H:%M:%S %Z %Y' ).ctime()
        except ValueError:
            # Leave it
            pass

        # Hyperlink the expt name to BaseSpace. We can't do this directly since there is an unpredictable
        # number in the URL but this will do.
        if 'Experiment Name' in self.run_params:
            self.run_params['Experiment Name'] = [
                                self.run_params['Experiment Name'].strip(),
                                "https://basespace.illumina.com/search/?type=run&query=" + \
                                                url_quote(self.run_params['Experiment Name']) ]

        self.sample_sheet = [ os.path.basename(
                                os.path.realpath(
                                  os.path.join( self.run_path_folder , 'SampleSheet.csv' ))),
                              os.path.realpath(
                                os.path.join( self.run_path_folder , 'SampleSheet.csv' )) ]

        # If the pipeline started actually demultiplexing we can get some other bits of info
        # The pipeline/start_times file contains the start time, as well as the version, and extra lines are added on each redo
        # It's written out directly by driver.sh just before it first triggers this script (to update the report
        # prior to running Snakefile.demux)
        self.pipeline_info = dict()
        try:
            with open(os.path.join( self.run_path_folder , 'pipeline/start_times')) as stfh:
                self.pipeline_info['start'] = list(stfh)[-1].rstrip('\n')

            if '@' in self.pipeline_info['start']:
                self.pipeline_info['version'], self.pipeline_info['start'] = \
                    self.pipeline_info['start'].split('@', 1)
            else:
                #If the version wasn't logged, this must have been 0.0.2 (or earlier)
                self.pipeline_info['version'] = '0.0.?'

            # Now if this script belong to a different version we need to say so, and we
            # end up with a version like 0.0.3+0.1.0. Redo the run from scratch if you need to
            # ensure consistency.
            if illuminatus_version != self.pipeline_info['version']:
                self.pipeline_info['version'] += "+" + illuminatus_version

            # If the pipeline started, the sequencer MUST have finished.
            touch_file = os.path.join( self.run_path_folder , 'RTAComplete.txt' )
            self.pipeline_info['Sequencer Finish'] = datetime.fromtimestamp(os.stat(touch_file).st_mtime).ctime()

        except FileNotFoundError:
            #OK, the pipeline didn't start
            pass

    def get_yaml(self):

        info = self.runinfo_xml
        params = self.run_params

        # Note that we can sometimes get the flowcell type from the params (Novoseq) and
        # otherwise from the info (everything else).

        idict = dict()

        idict['pre_start_info'] = {
                'Run Date': info['RunDate'],
                'LaneCount': int(info['LaneCount']),
                'Experiment Name': params['Experiment Name'],
                'Run ID': info['RunId'],
                'Instrument': info['Instrument'],
                'Flowcell Type' : params.get('Flowcell Type', info['FCType']),
                'Cycles':  info['Cycles'], # '251 [12] 251',
                't1//Run Start': params['Start Time'],
                'Pipeline Script': get_pipeline_script(),
                'Sample Sheet': self.sample_sheet # [ name, path ]
            }

        if self.pipeline_info:
            idict['post_start_info'] = {
                'Pipeline Version': self.pipeline_info['version'],
                't3//Pipeline Start': self.pipeline_info['start'],
                't2//Sequencer Finish': self.pipeline_info['Sequencer Finish']
            }

        return yaml.dump( idict,
                          Dumper = yamlloader.ordereddict.CSafeDumper,
                          default_flow_style = False )

def get_pipeline_script():
    return os.path.realpath(os.path.dirname(__file__)) + '/driver.sh'

if __name__ == '__main__':
    #If no run specified, examine the CWD.
    run = sys.argv[1] if len(sys.argv) > 1 else '.'
    run_info = RunMetaData(run)
    print ( run_info.get_yaml() )
