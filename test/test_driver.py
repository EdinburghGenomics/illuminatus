import unittest
import sys
import glob
import os

# import stuff from ../ directory
sys.path.insert(0,'../bin/')
global TEST_DATA
TEST_DATA = 'seqdata_examples'

class TestDiver(unittest.TestCase):

	def setUp( self ):
		os.system("mkdir -p " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/")
		os.system("rm " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/*")

	def test_reads_finished( self ):
		os.system("touch " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/")
		assert os.system("/home/mberinsk/workspace/illuminatus/bin/doall.sh | grep 160606_K00166_0102_BHF22YBBXX | grep READS_FINISHED") == 0
		
	def test_in_pipeline( self ):
		os.system("touch " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/lane{1..8}.started")
		assert os.system("/home/mberinsk/workspace/illuminatus/bin/doall.sh | grep 160606_K00166_0102_BHF22YBBXX | grep IN_PIPELINE" ) == 0

	def test_completed( self ):
		os.system("touch " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/lane{1..8}.done")
		assert os.system("/home/mberinsk/workspace/illuminatus/bin/doall.sh | grep 160606_K00166_0102_BHF22YBBXX | grep COMPLETE" ) == 0

class TestDriverNEW(unittest.TestCase):

	def setUp( self ):
		os.system("rm " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/*") 
		os.system("rmdir " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/")

	def test_new( self ):
		assert os.system("/home/mberinsk/workspace/illuminatus/bin/doall.sh | grep 160606_K00166_0102_BHF22YBBXX | grep NEW") == 0


if __name__ == '__main__':
	unittest.main()

