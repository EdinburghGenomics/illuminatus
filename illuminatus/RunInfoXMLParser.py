#!/usr/bin/env python3

import xml.etree.ElementTree as ET

class RunInfoXMLParser:
    """Uses the python xml parser to extract some run information and store it in a dictionary
    """
    def __init__( self , runinfo_file ):
        tree = ET.parse(runinfo_file)
        root = tree.getroot()
        self.read_and_length = {}
        self.read_and_indexed = {}

        self.run_info  = {}
        for read in root.iter('Read'):
            self.read_and_length[ read.attrib['Number']  ] = read.attrib[ 'NumCycles' ]
            # e.g.: read_and_length = { "1" : "301" , "2" : "8" , "3" : "8" , "4" : "301"} #
            self.read_and_indexed[ read.attrib['Number']  ] = read.attrib[ 'IsIndexedRead' ]
                        # e.g.: read_and_indexed = { "1" : "N" , "2" : "Y" , "3" : "Y" , "4" : "N"} #

        for read in root.iter('Run'):
            self.run_info[ 'RunId' ] = read.attrib['Id']

        for read in root.iter('FlowcellLayout'):
                        self.run_info[ 'LaneCount' ] = read.attrib['LaneCount']

        for read in root.iter('Instrument'):

            self.run_info[ 'Instrument' ] = read.text

            if self.run_info[ 'Instrument' ][0] == 'M':
                self.run_info[ 'Instrument' ] = 'miseq'
            elif self.run_info[ 'Instrument' ][0] == 'D':
                                self.run_info[ 'Instrument' ] = 'hiseq2500'
            elif self.run_info[ 'Instrument' ][0] == 'E':
                self.run_info[ 'Instrument' ] = 'hiseqX'
            elif self.run_info[ 'Instrument' ][0] == 'K':
                                self.run_info[ 'Instrument' ] = 'hiseq4000'

        for read in root.iter('Flowcell'):
            self.run_info[ 'Flowcell' ] = read.text

            if self.run_info[ 'Instrument' ] == 'miseq':
                try: # need to convert 00000000-AVHGC into AVHGC for miseq flowcells
                    self.run_info[ 'Flowcell' ].split("-")[1]
                except:
                    pass
