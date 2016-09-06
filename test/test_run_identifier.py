import unittest
import sys
import glob

# import stuff from ../ directory
sys.path.insert(0,'../bin/')

from RunInfo import RunInfo

class TestRunINFO(unittest.TestCase):

	TEST_DATA = 'seqdata_examples'

	def test_run_finished( self ):
		run = '150602_M01270_0108_000000000-ADWKV'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._is_sequencing_finished() == False

		run = '160603_M01270_0196_000000000-AKGDE'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._is_sequencing_finished() == True

		run = '160607_D00248_0174_AC9E4KANXX'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._is_sequencing_finished() == False

	def test_is_new_run( self ):
		run = '150602_M01270_0108_000000000-ADWKV'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._is_new_run() == True

		run = '160603_M01270_0196_000000000-AKGDE'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._is_new_run() == False

	def test_in_pipeline( self ):
		run = '160606_K00166_0102_BHF22YBBXX'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._was_started() == True

		run = '160603_M01270_0196_000000000-AKGDE'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._was_started() == False

	def test_is_restarted( self ):
		run = '160607_D00248_0174_AC9E4KANXX'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._was_restarted() == True

		run = '160606_K00166_0102_BHF22YBBXX'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._was_restarted() == False

	def test_is_finished( self ):
		run = '160607_D00248_0174_AC9E4KANXX'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._was_finished() == True

		run = '160606_K00166_0102_BHF22YBBXX'
		run_info = RunInfo(run, run_path = self.TEST_DATA)
		assert run_info._was_finished() == False

	def test_status( self ):
		#get status for all run folders
		runs = glob.glob('1*')
		for run in runs:
			run_info = RunInfo(run, run_path = self.TEST_DATA)
			#print run, run_info.get_status()

if __name__ == '__main__':
	unittest.main()

