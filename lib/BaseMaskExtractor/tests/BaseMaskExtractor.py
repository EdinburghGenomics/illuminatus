from RunInfoParser import RunInfoParser
from SampleSheetReader import SampleSheetReader

class BaseMaskExtractor:

	def __init__( self , samplesheet_file , runinfo_file ):
		self.rip = RunInfoParser( runinfo_file )
		#print runinfo_file, str(self.rip.read_and_length)
		self.ssr = SampleSheetReader( samplesheet_file )
		self.lane_length_dict = self.ssr.get_samplesheet_data_for_BaseMaskExtractor()
		#print self.lane_length_dict

	def get_base_mask_for_lane(self,lane):
		"""
		Calculates the BaseMask for a given lane.
		The function will read the run cycles from the RunInfo.xml and the index length from the SampleSheet(csv) file.

		Returns a string in the form of:
		"Y300n,I8,I8,Y300n"
		"Y300n,I10,Y300n"

		"""

		read1 = ""
		read2 = ""
		read3 = ""
		read4 = ""


		# how many reads do we have on this run?
		number_of_reads = len(self.rip.read_and_length)

		prefix  = ""
		postfix = ""

		if self.rip.read_and_indexed["1"] == "N":
			prefix  = "Y"
			postfix = "n"
	                cycles1 = int(self.rip.read_and_length["1"])
			read1 = prefix + str( cycles1 - 1 ) + postfix


                if self.rip.read_and_indexed["2"] == "N":
                        prefix  = "Y"
			postfix = "n"
                        cycles2 = int(self.rip.read_and_length["2"])
                        read2 = prefix + str( cycles2 - 1 ) + postfix
		elif self.rip.read_and_indexed["2"] == "Y":
                        prefix  = "I"
			postfix = ""
			cycles2 = int(self.rip.read_and_length["2"])
			index_1_length = self.lane_length_dict[lane][0]
			#if index_1_length == 0:
			#	index_1_length = 6
			if index_1_length == 0:
				if number_of_reads > 2:
					postfix = postfix.rjust(cycles2, 'n')
					if number_of_reads > 3:
						postfix = "I" + str(cycles2)
	                        	read2 = postfix
				else:
					padding = ( cycles2 - 6 )
	                                postfix = postfix.rjust(padding, 'n')
					read2 = prefix + str( cycles2 - padding ) + postfix
			elif ( cycles2 - index_1_length ) > 0:
				padding = ( cycles2 - index_1_length )
				postfix = postfix.rjust(padding, 'n')
                                read2 = prefix + str( cycles2 - padding ) + postfix
			else:
				read2 = prefix + str( cycles2 - 0 ) + postfix

		if number_of_reads > 2:
	                if self.rip.read_and_indexed["3"] == "N":
        	                prefix  = "Y"
				postfix = "n"
        	                cycles3 = int(self.rip.read_and_length["3"])
        	                read3 = prefix + str( cycles3 - 1 ) + postfix
        	        elif self.rip.read_and_indexed["3"] == "Y":
                	        prefix  = "I"
				postfix = ""
	                        cycles3 = int(self.rip.read_and_length["3"])
	                        index_2_length = self.lane_length_dict[lane][1]
				#print index_1_length, index_2_length,cycles3,number_of_reads
	                        if index_2_length == 0:
        	                        if number_of_reads > 3:
                	                        postfix = postfix.rjust(cycles3, 'n')
						if index_1_length == 0:
		                                	postfix = "I" + str(cycles3)
                        	                read3 = postfix
                                	else:
                                        	read3 = prefix + str( cycles3 - 0 ) + postfix
	                        elif ( cycles3 - index_2_length ) > 0:
        	                        padding = ( cycles3 - index_1_length )
                	                postfix = postfix.rjust(padding, 'n')
                        	        read3 = prefix + str( cycles3 - padding ) + postfix
	                        else:
			                read3 = prefix + str( cycles3 - 0 ) + postfix
	
		if number_of_reads > 3:
	                if self.rip.read_and_indexed["4"] == "N":
        	                prefix  = "Y"
                	        postfix = "n"
                        	cycles4 = int(self.rip.read_and_length["4"])
	                        read4 = prefix + str( cycles4 - 1 ) + postfix
	                elif self.rip.read_and_indexed["4"] == "Y":
        	                prefix  = "I"
                	        postfix = ""
                        	cycles4 = int(self.rip.read_and_length["4"])
	                        read4 = prefix + str( cycles4 - 0 ) + postfix

		base_mask = str(read1) + "," + str(read2)
                if len(read3) > 0:
			base_mask = base_mask + "," + str(read3)
		if len(read4) > 0:
			base_mask = base_mask + "," + str(read4)

		print lane + ":" + base_mask
		return base_mask
