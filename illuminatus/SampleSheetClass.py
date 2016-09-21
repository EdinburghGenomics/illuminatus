#!/usr/bin/env python3

from __future__ import division,print_function,absolute_import
import sys
import glob
import csv
from io import StringIO
from datetime import date
import os

from xml.dom.minidom import parseString

class SampleSheetPrinter:

    def __init__(self,samplesheet):
        self.samplesheet = samplesheet
        self.max_index_lengths = self._get_max_sequence_length() # [ index1 , index2 ]
        self.DEFAULT_PADDING = 5
        self.DEFAULT_NAME = 'DummyIndex'

    def _get_max_sequence_length(self):
        index1_max_length = 0
        index2_max_length = 0
        lane_number = 0
        for lane in self.samplesheet.lanes:
            lane_number = lane_number + 1
            for pool in lane.pools:
                for lib in pool.libraries:
                    if len(lib.index1_sequence) > index1_max_length: index1_max_length = len(lib.index1_sequence)
                    if len(lib.index2_sequence) > index2_max_length: index2_max_length = len(lib.index2_sequence)
        return [index1_max_length , index2_max_length]

    def _printPaddedIndexes(self,library, concatenate_indexes = True):
        if self.max_index_lengths[0] == 0:
            index1 = library.index1_sequence.ljust(self.DEFAULT_PADDING, "N")
        index1 = library.index1_sequence.ljust(self.max_index_lengths[0], "N")
        index2 = library.index2_sequence.ljust(self.max_index_lengths[1], "N")
        delimiter = ""
        if self.max_index_lengths[1] > 0: delimiter = "-"

        if concatenate_indexes:
            return index1 + delimiter + index2
        else:
            return [index1 , index2]

    def _printPaddedIndexNames(self,library, concatenate_indexes = True):
        name1 = library.index1_name
        name2 = library.index2_name

        if self.max_index_lengths[0] == 0:
            name1 = self.DEFAULT_NAME
        if not self.max_index_lengths[1] == 0 and name2 == "":
            name2 = self.DEFAULT_NAME

        delimiter = ""
        if self.max_index_lengths[1] > 0: delimiter = "_"

        if concatenate_indexes:
            return name1 + delimiter + name2
        else:
            return [name1 , name2]

    def writeSampleSheetCSV(self,filename):
        contents = self.to_csv()
        with open(filename, 'w') as f:
            f.write(contents)

    def to_csv(self):
        return self._csv_header() + self._csv_data()

    def _csv_header(self):
        raise NotImplemented

    def _csv_data(self):
        raise NotImplemented

    def _csv_data_headings(self):
        raise NotImplemented

class HiseqSampleSheetPrinter(SampleSheetPrinter):

    def to_csv(self):
        # Hiseq2500 has no header
        return self._csv_data()

    def _csv_data(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        # Write headings
        writer.writerow(self._csv_data_headings())
        lane_number = 0
        for lane in self.samplesheet.lanes:
            lane_number = lane_number + 1
            for pool in lane.pools:
                for lib in pool.libraries:
                    row = [
                        self.samplesheet.flowcell_id,                # FCID
                        lane_number,                        # Lane
                        lib.library_name,                    # SampleID
                        pool.pool_name if len(pool.pool_name)>0 else "XXX",    # SampleRef
                        self._printPaddedIndexes(lib),                # Index
                        self._printPaddedIndexNames(lib),            # Description
                        'N',                            # Control
                        '',                            # Recipe
                        self.samplesheet.operator,                # Operator
                        lib.library_project                    # SampleProject
                    ]
                    writer.writerow(row)

        return output.getvalue()

    def _csv_data_headings(self):

        headings = ['FCID','Lane','SampleID', 'SampleRef', 'Index', 'Description',
            'Control','Recipe', 'Operator','SampleProject']

        return headings


class MiseqSampleSheetPrinter(SampleSheetPrinter):

    def _csv_header(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        rows = [
        ['[Header]'],
            ['IEMFileVersion', '4'],
            ['Investigator Name', self.samplesheet.operator],
            ['Project Name'],
        ['Experiment Name', self.samplesheet.experiment_name],
        ['Date', date.today().strftime('%-m/%-d/%Y')],
        ['Workflow', self.samplesheet.workflow],
        ['Application', self.samplesheet.application],
        ['Assay', self.samplesheet.assay],
        ['Description'],
        ['Chemistry', "Default"],
        [],
        ['[Reads]'],
        [self.samplesheet.read1cycles],
        ]

        if len(self.samplesheet.read2cycles) > 0:
            rows.append([self.samplesheet.read2cycles])

        rows.append([])
        rows.append(['[Settings]'])

        rows.append([])
        rows.append(['[Data]'])

        writer.writerows(rows)
        return output.getvalue()

    def _csv_data(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        # Write headings
        writer.writerow(self._csv_data_headings())

        for lane in self.samplesheet.lanes:
            for pool in lane.pools:
                for lib in pool.libraries:
                    row = [
                        lib.library_name,            # Sample_ID
                        pool.pool_name if len(pool.pool_name)>0 else "",             # Sample_Name
                        self.samplesheet.flowcell_id,        # Sample_Plate
                        '',                     # Sample_Well
                        lib.library_project,            # Sample_Project
                        self._printPaddedIndexes(lib,concatenate_indexes = False)[0],        # index
                        self._printPaddedIndexNames(lib,concatenate_indexes = False)[0]        # I7_Index_ID
                    ]

                    if self.samplesheet.use_dual_indexes():
                        row.extend([
                            self._printPaddedIndexes(lib,concatenate_indexes = False)[1],        # index2
                            self._printPaddedIndexNames(lib,concatenate_indexes = False)[1]        # I5_Index_ID
                        ])

                    row.append(self.samplesheet.operator)         # Description
                    writer.writerow(row)

        return output.getvalue()


    def _csv_data_headings(self):

        headings = ['Sample_ID', 'Sample_Name', 'Sample_Plate', 'Sample_Well',
            'Sample_Project','index', 'I7_Index_ID']

        if self.samplesheet.use_dual_indexes():
            headings.extend(['index2', 'I5_Index_ID'])

        headings.append('Description')

        return headings

class Hiseq4000SampleSheetPrinter(MiseqSampleSheetPrinter):
    def _csv_header(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        rows = [
        ['[Header]'],
        ['IEMFileVersion', '4'],
        ['Investigator Name', self.samplesheet.operator],
        ['Project Name'],
        ['Date', date.today().strftime('%-m/%-d/%Y')],
        ['Description'],
        [],
        ]

        rows.append([])
        rows.append(['[Settings]'])

        rows.append([])
        rows.append(['[Data]'])

        writer.writerows(rows)
        return output.getvalue()

    def _csv_data(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        # Write headings
        writer.writerow(self._csv_data_headings())

        for lane in self.samplesheet.lanes:
            for pool in lane.pools:
                for lib in pool.libraries:
                    row = [
                        lane.lane_number,                               # Lane
                        lib.library_name,                               # Sample_ID
                        pool.pool_name if len(pool.pool_name)>0 else "",            # Sample_Name
                        self.samplesheet.flowcell_id,                       # Sample_Plate
                        '',                                     # Sample_Well
                        self._printPaddedIndexes(lib,concatenate_indexes = False)[0],       # index
                        self._printPaddedIndexNames(lib,concatenate_indexes = False)[0],    # I7_Index_ID
                        lib.library_project,                            # Sample_Project
                    ]

                    if self.samplesheet.use_dual_indexes():
                        row.extend([
                            self._printPaddedIndexes(lib,concatenate_indexes = False)[1],   # index2
                            self._printPaddedIndexNames(lib,concatenate_indexes = False)[1] # I5_Index_ID
                        ])

                    row.append(self.samplesheet.operator)                        # Description
                    writer.writerow(row)

        return output.getvalue()

    def _csv_data_headings(self):

        headings = ['Lane','Sample_ID','Sample_Name','Sample_Plate','Sample_Well','I7_Index_ID','index','Sample_Project']

        if self.samplesheet.use_dual_indexes():
            headings.extend(['index2', 'I5_Index_ID'])

        headings.append('Description')

        return headings


class HiseqXSampleSheetPrinter(Hiseq4000SampleSheetPrinter):

    def to_csv(self):
        self._reverse_complement_all_index2()
        return self._csv_header() + self._csv_data()

    def _get_sequence_reverse_complement(self, seq):
        # returns a reverse complement of a given sequence
        # adapted from
        # http://crazyhottommy.blogspot.co.uk/2013/10/python-code-for-getting-reverse.html
        rev_seq = ""
        seq_dict = { "A":"T", "T":"A", "C":"G", "G":"C", "a":"t", "t":"a", "c":"g", "g":"c" }
        for base in seq:
            if base not in 'ATCGatcg':
                return None

            rev_seq="".join([seq_dict[base] for base in reversed(seq)])
            return rev_seq
    def _reverse_complement_all_index2(self):
        for lane in self.samplesheet.lanes:
            for pool in lane.pools:
                for lib in pool.libraries:
                    lib.index2_sequence = self._get_sequence_reverse_complement(lib.index2_sequence)

        

class Hiseq2500SampleSheetPrinter(HiseqSampleSheetPrinter):
    def printme(self):
        print ("aaa")

class Hiseq2500RapidSampleSheetPrinter(HiseqSampleSheetPrinter):
    def printme(self):
        print ("aaa")


'''
    SampleSheet Class Declaration
'''


class SampleSheet:

    def __init__(self):
        self.lanes = []
        self.flowcell_id = ""
        self.operator = ""
        self.read1cycles = ""
        self.read2cycles = ""
        self.experiment_name = ""
        self.workflow = "GenerateFASTQ"
        self.application = "FASTQ Only"
        self.assay = "TruSeq DNA"
        self.chemistry = "Default"

    def addLane(self):
        self.lanes.append(Lane( len(self.lanes) ))

    def setFlowcellID(self, fcid):
        self.flowcell_id = fcid

    def setOperator(self, operator):
        self.operator = operator

    def use_dual_indexes(self):
        for lane in self.lanes:
            for pool in lane.pools:
                for lib in pool.libraries:
                    if len(lib.index2_sequence)>0:
                        return True
        return False


class Lane:
    def __init__(self, lane_number):
        self.lane_number = lane_number+1
        self.pools = []

    def addPool(self, pool_name ):
        pool = Pool(pool_name)
        self.pools.append( pool )



class Pool:
    def __init__(self, name):
        self.pool_name = name
        self.libraries = []

    def addLibrary(self, library_name):
        library = Library(library_name)
        self.libraries.append( library )
        return self.pool_name


class Library:
    def __init__(self, name):
        self.library_name = name
        self.library_pool = ""

        self.index1_sequence = ""
        self.index2_sequence = ""
        self.index1_name = ""
        self.index2_name = ""

        self.library_project = ""

    def setName(self, name):
        self.library_name = name

    def setIndexSequence1(self, seq):
        self.index1_sequence = seq

    def setIndexSequence2(self, seq):
        self.index2_sequence = seq

    def setIndexName1(self, seq):
        self.index1_name = seq

    def setIndexName2(self, seq):
        self.index2_name = seq

    def setProject(self):
        self.library_project = self.library_name[0:5]


