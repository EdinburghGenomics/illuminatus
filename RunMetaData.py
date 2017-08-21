#!/usr/bin/env python3
import os, sys
from glob import glob
from collections import defaultdict
from datetime import datetime

import yaml

from illuminatus.RunInfoXMLParser import RunInfoXMLParser
from illuminatus.RunParametersXMLParser import RunParametersXMLParser

class RunMetaData:
    """This Class provides information about a sequencing run, given a run folder.
       It is very similar to RunInfo.py but does not attempt to determine
       the processing status of the run.
       It will parse information from the following sources:
         RunInfo.xml file
    """
    def __init__( self , run_folder , run_path = '' ):

        # here the RunInfo.xml is parsed into an object
        self.run_path_folder = os.path.join( run_path , run_folder )
        runinfo_xml_location = os.path.join( self.run_path_folder , 'RunInfo.xml' )
        try:
            rip = RunInfoXMLParser( runinfo_xml_location )
            self.runinfo_xml = rip.run_info
        except Exception:
            #if we can't read it we can't get much info
            #contrast this with RunInfo.py which always returns something.
            raise

        try:
            runparams_xml = RunParametersXMLParser( os.path.join( self.run_path_folder , 'runParameters.xml' ) )
            self.run_params = runparams_xml.run_parameters
        except Exception:
            #we can usefully run without this
            self.run_params = defaultdict(lambda: 'unknown')

        self.sample_sheet = [ os.path.basename(
                                os.path.realpath(
                                  os.path.join( self.run_path_folder , 'SampleSheet.csv' ))),
                              os.path.realpath(
                                os.path.join( self.run_path_folder , 'SampleSheet.csv' )) ]

        #If the pipeline is started we can get some other bits of info
        #The .started files don't get removed. Report the mtime of the latest one.
        self.pipeline_info = dict()
        started_times = sorted( os.stat(f).st_mtime for f in
                                glob(os.path.join( self.run_path_folder , 'pipeline/lane?.started' )) )
        if started_times:
            self.pipeline_info['start'] = datetime.fromtimestamp(started_times[-1]).ctime()

            touch_file = os.path.join( self.run_path_folder , 'RTAComplete.txt' )
            self.pipeline_info['Sequencer Finish'] = datetime.fromtimestamp(os.stat(touch_file).st_mtime).ctime()


    def get_yaml(self):

        info = self.runinfo_xml
        params = self.run_params
        idict = dict()

        idict['pre_start_info'] = {
                'Run Date': info['Run Date'],
                'LaneCount': int(info['LaneCount']),
                'Experiment Name': params['Experiment Name'],
                'Run ID': [ info['RunId'], 'https://genowiki.is.ed.ac.uk/display/GenePool/{}'.format(info['RunId']) ],
                'Machine': info['Instrument'],
                'Cycles':  info['Cycles'], # '251 [12] 251',
                'Start Time': params['Start Time'],
                'Pipeline Script': get_pipeline_script(),
                'Sample Sheet': self.sample_sheet # [ name, path ]
            }

        if self.pipeline_info:
            idict['post_start_info'] = {
                'Pipeline Version': get_pipeline_version(),
                'Pipeline Start': self.pipeline_info['start'],
                'Sequencer Finish': self.pipeline_info['Sequencer Finish'],
            }

        return yaml.safe_dump(idict, default_flow_style=False)

def get_pipeline_version():
    try:
        with open( os.path.dirname(__file__) + '/version.txt') as vfh:
            return vfh.read().strip()
    except Exception:
        return '0.0.0'

def get_pipeline_script():
    return os.path.realpath(os.path.dirname(__file__)) + '/driver.sh'

if __name__ == '__main__':
    #If no run specified, examine the CWD.
    run = sys.argv[1] if len(sys.argv) > 1 else '.'
    run_info = RunMetaData(run)
    print ( run_info.get_yaml() )
