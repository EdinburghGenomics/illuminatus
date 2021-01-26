#!/usr/bin/env python3

import logging as L
import csv, sys, os
from itertools import zip_longest

from .SampleSheetClass import SampleSheet

class SampleSheetReader:

    def __init__( self , SampleSheetFile ):
        # sets self.headers, self.column_mapping, self.samplesheet_data
        self._get_lines_from_ssfile( SampleSheetFile )
        '''
         e.g.:
        self.column_mapping =
        {
        'index': 5,
        'description': 9,
        'sample_id': 0,
        'sample_plate': 2,
        'i7_index_id': 6,
        'sample_well': 3,
        'sample_project': 4,
        'sample_name': 1,
        'index2': 7,
        'i5_index_id': 8
        }
        '''
        self.samplesheet = self._get_samplesheet_data_object_from_column_mapping()

    def get_index_lengths_by_lane(self):
        '''
        Was get_samplesheet_data_for_BaseMaskExtractor

        will return
        { "lane_number" : [ index1length , index2length ] }

        '''
        lane_number_index_length = {}

        for row in self.samplesheet_data:
            lane = self._get_lane_from_data_row( row , self.column_mapping )
            index_sequences = self._get_index_sequences_from_data_row( row , self.column_mapping )

            # What if the indexes are different lengths? This should not happen, but logically
            # we have to return the max values, I think...
            lane_number_index_length[ lane ] = [ max(i) for i in zip_longest(
                                    lane_number_index_length.get(lane, []),
                                    [ len(i) for i in index_sequences ],
                                    fillvalue = 0 ) ]

        return lane_number_index_length

    def _get_lines_from_ssfile( self , SampleSheetFile ):
        csvFile = SampleSheetFile
        with open(csvFile, newline='') as csvFH:
            csvData = csv.reader(csvFH, delimiter=',')
            self.column_mapping = None
            in_section = None
            self.headers = {}
            self.samplesheet_data = []
            for row in csvData:
                try:
                    if not row or row[0] == '':
                        continue

                    if row[0].startswith('['):
                        in_section = row[0].lower().strip('[]')
                        continue

                    if in_section == 'header':
                        if len(row) > 1:
                            self.headers[row[0]] = row[1]
                        else:
                            self.headers[row[0]] = ''

                    if in_section == 'data':
                        if not self.column_mapping:
                            # Data header line
                            assert "Sample_ID" in row or "SampleID" in row
                            self.column_mapping = { f.lower(): idx for idx, f in enumerate(row) }
                        else:
                            self.samplesheet_data.append( row )

                except Exception:
                    #FIXME - do we really want to swallow this exception?
                    e = str( sys.exc_info()[0] ) +": " + str( sys.exc_info()[1] )
                    L.error("while reading "+ csvFile + "\t" + e)

        assert self.column_mapping, "No [Data] found in {}".format(csvFile)

    def _get_samplesheet_data_object_from_column_mapping(self):
        '''
        The Samplesheet data and column headers are now in memory and are passed on to this function.
        Will construct a general SampleSheet Object that can then be used to access Lanes/Pools/Indexes/etc.
        '''
        samplesheet = SampleSheet()

        for row in self.samplesheet_data:
            lane = self._get_lane_from_data_row( row , self.column_mapping )
            index_sequences = self._get_index_sequences_from_data_row( row , self.column_mapping )

        # todo: should return a real SampleSheet object here after filling it up
        return samplesheet

    def _get_lane_from_data_row( self , row , column_header_mapping ):
        '''
        The function will extract and return the number of the lane contained in the provided samplesheet row.
        If no lane is found will return 1 (because MiSeq SampleSheets don't have explicit lane number).
        '''
        try:
            lane_number = row[ column_header_mapping['lane'] ]
        except KeyError:
            lane_number = "1" # default
        return lane_number

    def _get_index_sequences_from_data_row( self , row , column_header_mapping ):
        '''
        The function will extract and return the index-sequences contained in the provided samplesheet row.
        If no index is found will return an empty string.
           returns [ index_1_sequence , index_2_sequence ]
        '''

        index2 = ""
        # get index 1
        try:
            index1 = row[ column_header_mapping['index'] ]
            #index1 = index1.replace("N","")
            #index1 = index1.rstrip('N')
            if "-" in index1:
                tmp = index1
                index1 = tmp.split("-")[0]
                index2 = tmp.split("-")[1]
        except KeyError:
                index1 = ""

        #get index 2
        if len(index2) == 0:
            try:
                    index2 = row[ column_header_mapping['index2'] ]
                #index2 = index2.rstrip('N')
                #index2 = index2.replace("N","")
            except KeyError:
                index2 = ""

        # don't remove the N's from a sequence entirely NNNNNN 
        # but remove from the end of e.g. AGTACNN
        if len( index1.rstrip('N') ) > 0:
            index1 = index1.rstrip('N')

        if len( index1.rstrip('N') ) > 0: # if the first index is a dummy index, will assume second must be a dummy index
            index2 = index2.rstrip('N')

        return [index1 , index2]


def main():
    """Only for testing. You can't just run this script directly, but you can do:
        python3 -m illuminatus.SampleSheetReader /path/to/SampleSheet.csv
    """

    ssr = SampleSheetReader(sys.argv[1])

    print("Read SampleSheet: %s" % sys.argv[1])

    print("Column mapping:   %s" % ssr.column_mapping)
    print("Mapping data:")
    for l in ssr.samplesheet_data:
        print("    %s" % l)
    print("Samplesheet:      %s" % repr(ssr.samplesheet))

if __name__ == '__main__':
    main()
