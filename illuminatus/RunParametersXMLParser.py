#!/usr/bin/env python3

import os, sys
from glob import glob
from datetime import datetime
import xml.etree.ElementTree as ET
import yaml

class RunParametersXMLParser:
    """Uses the python xml parser to extract some run information and store it in a dictionary
    """
    def __init__( self , runparameters_file ):

        # So it turns out that if I copy a run from the NovaSeq there is no RunParameters.xml
        # file and this is annoying. Allow me to provide a RunParameters.OVERRIDE.yml
        # file that sets everything directly.
        for f in [ "pipeline/runParameters.OVERRIDE.yml",
                   "pipeline/RunParameters.OVERRIDE.yml",
                   "runParameters.OVERRIDE.yml",
                   "RunParameters.OVERRIDE.yml" ]:
            rf = os.path.join( runparameters_file, f )
            if os.path.exists(rf):
                runparameters_file = rf
                break
        if runparameters_file.endswith(".yml"):
            self.make_from_yaml(runparameters_file)
            return

        # If given a directory, look for the file, which may have different names
        # depending on the sequencer.
        for f in [ "runParameters.xml",
                   "RunParameters.xml" ]:
            rf = os.path.join( runparameters_file, f )
            if os.path.exists(rf):
                runparameters_file = rf
                break
        self.make_from_xml(runparameters_file)

    def make_from_xml(self, runparameters_file):
        tree = ET.parse(runparameters_file)
        root = tree.getroot()

        self.run_parameters = {}

        for e in root.iter('ExperimentName'):
            self.run_parameters[ 'Experiment Name' ] = e.text

        # On the HiSeq we can read Flowcell and on NovaSeq we can read FlowCellMode
        for e in root.iter('Flowcell'):
            self.run_parameters[ 'Flowcell Type' ] = e.text
        for e in root.iter('FlowCellMode'):
            self.run_parameters[ 'Flowcell Type' ] = e.text

        # On the newer NovaSeq runs we can get the chemistry version
        for e in root.iter('SbsConsumableVersion'):
            self.run_parameters[ 'Consumable Version' ] = e.text

        #The start time is the timestamp of the file, or else the oldest file in the Recipe dir
        started_times = sorted( os.stat(f).st_mtime for f in
                                [runparameters_file] +
                                glob(os.path.join( os.path.dirname(runparameters_file) , 'Recipe', '*' )) )
        self.run_parameters[ 'Start Time' ] = int(started_times[0])

    def make_from_yaml(self, runparameters_file):

        with open(runparameters_file) as yfh:
            rp_from_yaml = yaml.safe_load(yfh)

        rp = { 'Experiment Name': 'unset',
               'Start Time': None,
               'Consumable Version': '0',
               'Flowcell Type': None }

        rp.update(rp_from_yaml)

        # Eliminate None values
        for k in list(rp):
            if rp[k] is None:
                del rp[k]

        self.run_parameters = rp

# Self-test mode
if __name__ == "__main__":
    rpxp = RunParametersXMLParser(*(sys.argv[1:] or ['.']))

    print(yaml.safe_dump(rpxp.run_parameters), end='')
