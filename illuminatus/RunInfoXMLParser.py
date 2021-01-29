#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET

from datetime import datetime

instrument_types = "M:miseq D:hiseq2500 E:hiseqX K:hiseq4000 A:novaseq"

# Note that for NovoSeq the type is explicitly given in RunParameters.xml, and in fact
# for SP flowcells we have to look here. See summarize_lane_contents.py
flowcell_types = { # MiSeq types
                   "1/1/1/2"  : "Nano",
                   "1/2/1/4"  : "Micro",
                   "1/2/1/14" : "Normal v2",
                   "1/2/1/19" : "Normal v3",

                   # NovaSeq types
                   "2/2/2/78" : "S1",
                   "2/2/4/88" : "S2",
                   "4/2/6/78" : "S4",
                }

class RunInfoXMLParser:
    """Uses the python xml parser to extract some run information and store it in a dictionary
    """

    def __init__( self , runinfo_file ):

        # If given a directory, look for the file inside
        # Currently there is only one possible name
        if os.path.isdir(runinfo_file):
            runinfo_file = os.path.join( runinfo_file, "RunInfo.xml" )

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
            self.run_info[ 'LaneCount' ] = int(read.attrib['LaneCount'])

        itypes = dict( i.split(':') for i in (instrument_types).split())
        for read in root.iter('Instrument'):

            self.run_info[ 'Instrument' ] = read.text

            try:
                self.run_info['Instrument'] = itypes[self.run_info['Instrument'][:1]] + '_' + self.run_info['Instrument']
            except KeyError:
                pass

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
                self.run_info[ 'RunDate' ] = '{}-{}-{}'.format(d[6:10], d[0:2], d[3:5])
            elif d[1] == '/':
                # For Jan-Sep
                self.run_info[ 'RunDate' ] = '{}-0{}-{}'.format(d[5:9], d[0:1], d[2:4])
            elif len(d) == 6:
                # The date is in format YYMMDD but we want YYYY-MM-DD
                self.run_info[ 'RunDate' ] = '20{}-{}-{}'.format(d[0:2], d[2:4], d[4:6])
            else:
                # Dunno. Just use it unmodified.
                self.run_info[ 'RunDate' ] = d

        self.run_info[ 'FCType' ] = self.get_flowcell_type(root)

    def get_flowcell_type(self, root):
        """See what type of flowcell this is by the geometry. If it is recognised, give it a name.
           Looking for something like: <FlowcellLayout LaneCount="1" SurfaceCount="2" SwathCount="1" TileCount="14" />
        """
        try:
            e, = root.iter('FlowcellLayout')
            layout = e.attrib
        except Exception:
            return "Unknown"

        # Simplify
        slayout = '/'.join( layout.get(x + "Count", '?') for x in "Lane Surface Swath Tile".split() )
        return flowcell_types.get(slayout, slayout)

