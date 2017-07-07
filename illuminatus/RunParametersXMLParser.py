#!/usr/bin/env python3

import os
from glob import glob
from datetime import datetime
import xml.etree.ElementTree as ET

class RunParametersXMLParser:
    """Uses the python xml parser to extract some run information and store it in a dictionary
    """
    def __init__( self , runparameters_file ):
        tree = ET.parse(runparameters_file)
        root = tree.getroot()

        self.run_parameters = {}


        for e in root.iter('ExperimentName'):
            self.run_parameters[ 'Experiment Name' ] = e.text

        #The start time is the timestamp of the file, or else the oldest file in the Recipe dir
        started_times = sorted( os.stat(f).st_mtime for f in
                                [runparameters_file] +
                                glob(os.path.join( os.path.dirname(runparameters_file) , 'Recipe', '*' )) )
        self.run_parameters[ 'Start Time' ] = datetime.fromtimestamp(started_times[0]).ctime()
