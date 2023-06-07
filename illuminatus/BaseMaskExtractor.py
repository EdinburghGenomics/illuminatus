#!/usr/bin/env python3

import logging as L

from .RunInfoXMLParser import RunInfoXMLParser
from .SampleSheetReader import SampleSheetReader

class BaseMaskExtractor:

    def __init__( self , samplesheet_file , runinfo_file ):
        self.rip = RunInfoXMLParser( runinfo_file )
        L.debug(f"{runinfo_file} : {self.rip.read_and_length}")
        self.ssr = SampleSheetReader( samplesheet_file )
        self.lane_length_dict = self.ssr.get_index_lengths_by_lane()
        L.debug(f"LLD = {self.lane_length_dict}")

    def get_lanes(self):
        """Returns an ordered list of all lanes in the SampleSheet
        """
        return sorted(self.lane_length_dict.keys())

    def get_base_mask_for_lane(self,lane):
        """
        Calculates the BaseMask for a given lane.
        The function will read the run cycles from the RunInfo.xml and the index length from the SampleSheet(csv) file.

        Returns a string in the form of:
        "Y300n,I8,I8,Y300n"
        "Y300n,I10,Y300n"

        """
        lane = str(lane)

        # how many reads do we have on this run?
        number_of_reads = len(self.rip.read_and_length)


        # different approach
        base_mask = ""
        indexed_read_counter = 0
        delimiter=""
        read_nr = 0
        while (read_nr < number_of_reads):
            read_nr = read_nr + 1
            read_cycles = int( self.rip.read_and_length[ str(read_nr) ] ) # read cycles from the RunInfo.xml

            #print ( self.lane_length_dict )
            #print (lane)
            #print (indexed_read_counter)

            if self.rip.read_and_indexed[ str(read_nr) ] == "N":
                #this is a data-read (not index)
                base_mask = base_mask + delimiter + "Y" + str( read_cycles - 1 )+"n"
            elif self.rip.read_and_indexed[ str(read_nr) ] == "Y":
                index_read_length = int( self.lane_length_dict[lane][ indexed_read_counter ] ) # index length from the samplesheet
                #this is an indexed read
                if read_cycles == index_read_length:
                    # consider all cycles as index
                    base_mask = base_mask + delimiter + "I" + str(index_read_length)
                elif read_cycles > index_read_length:
                    if index_read_length == 0:
                        # no index/dummyindex was provided, ignore all cylces of this read by setting "n*"
                        base_mask = base_mask + delimiter + "n*"
                    else:
                        # consider index by setting "Ix", ignore the remaining cycles after the index "n*"
                        base_mask = base_mask + delimiter + "I" + str(index_read_length) + "n*"
                elif read_cycles < index_read_length:
                    # the index is longer than cycles of this read so will only consider the cycles avaialble
                    base_mask = base_mask + delimiter + "I" + str(read_cycles)
                indexed_read_counter = indexed_read_counter + 1

            if len(base_mask) > 0:
                delimiter = ","
            #print ( base_mask )
        # end different approach

        return base_mask


        ##############################################################################

