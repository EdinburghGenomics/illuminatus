#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET

from datetime import datetime

instrument_types = "M:miseq D:hiseq2500 E:hiseqX K:hiseq4000 A:novaseq".split()

class RunInfoXMLParser:
    """Uses the python xml parser to extract some run information and store it in a dictionary
    """

    def __init__( self , runinfo_file ):

        # If given a directory, look for the file inside
        # Currently there is only one possible name
        for f in "RunInfo.xml".split():
            ri = os.path.join( runinfo_file, f )
            if os.path.exists(ri):
                runinfo_file = ri
                break

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

        self.run_info[ 'Cycles' ] = ' '.join( ("{}" if self.read_and_indexed.get(k) != 'Y' else
                                               "[{}]").format(self.read_and_length[k])
                                              for k in sorted(self.read_and_length.keys(), key=int) )
        for read in root.iter('Run'):
            self.run_info[ 'RunId' ] = read.attrib['Id']

        for read in root.iter('FlowcellLayout'):
            self.run_info[ 'LaneCount' ] = read.attrib['LaneCount']

        for read in root.iter('Instrument'):

            self.run_info[ 'Instrument' ] = read.text

            for idmap in instrument_types:

                if self.run_info['Instrument'].startswith(idmap[0]):
                    self.run_info['Instrument'] = idmap[2:] + '_' + self.run_info['Instrument']
                    continue

        for read in root.iter('Flowcell'):
            if '-' in read.text:
                # need to convert 00000000-AVHGC into AVHGC for miseq flowcells
                self.run_info[ 'Flowcell' ] = read.text.split("-")[1]
            else:
                self.run_info[ 'Flowcell' ] = read.text

        for date_elem in root.iter('Date'):
            d = date_elem.text
            if d[2] == '/':
                # Novaseq runs are being dated like '11/24/2017 4:52:13 AM'
                self.run_info[ 'Run Date' ] = '{}-{}-{}'.format(d[6:10], d[0:2], d[3:5])
            elif len(d) == 6:
                # The date is in format YYMMDD but we want YYYY-MM-DD
                self.run_info[ 'Run Date' ] = '20{}-{}-{}'.format(d[0:2], d[2:4], d[4:6])
            else:
                # Dunno. Just use it unmodified.
                self.run_info[ 'Run Date' ] = d


