import xml.etree.ElementTree as ET

class RunInfoParser:
	def __init__( self , runinfo_file ):
		tree = ET.parse(runinfo_file)
		root = tree.getroot()
		self.read_and_length = {}
		self.read_and_indexed = {}
		for read in root.iter('Read'):
			self.read_and_length[ read.attrib['Number']  ] = read.attrib[ 'NumCycles' ]
			# e.g.: read_and_length = { "1" : "301" , "2" : "8" , "3" : "8" , "4" : "301"} #
			self.read_and_indexed[ read.attrib['Number']  ] = read.attrib[ 'IsIndexedRead' ]
                        # e.g.: read_and_indexed = { "1" : "N" , "2" : "Y" , "3" : "Y" , "4" : "N"} #

