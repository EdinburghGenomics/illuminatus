import unittest
import sys
import glob

# import stuff from ../ directory
sys.path.insert(0,'../bin/')

from RunInfo import RunInfo

class TestRunINFO(unittest.TestCase):

    #Helper functions:
    def use_run(self):
        """Copies a selected run into a temporary folder
           and sets self.current_run to the run id and
           self.run_dir to the temporary dir.
        """
        cleanup_run()

	    TEST_DATA = 'seqdata_examples'

        lalalala
        #Make a temp dir
        #Clone the run folder into it
        #Set the variables

    def cleanup_run(self):
        """If self.run_dir has been set, delete the temporary
           folder.
        """
        if vars(self).get('run_dir'):
            rmrf(self.run_dir)
            self.run_dir = None

    def tearDown(self):
        """Avoid leaving temp files around.
        """
        cleanup_run()

	def test_run_finished( self ):
        """TODO - add comment here
        """

        use_run('150602_M01270_0108_000000000-ADWKV')
        #Now you can change the files in self.run_dir if you like
		run_info = RunInfo(self.current_run, run_path = self.run_dir)
		self.assertFalse(run_info._is_sequencing_finished())

		use_run('160603_M01270_0196_000000000-AKGDE')
		run_info = RunInfo(self.current_run, run_path = self.run_dir)
		self.assertTrue(run_info._is_sequencing_finished())

		use_run('160607_D00248_0174_AC9E4KANXX')
		run_info = RunInfo(self.current_run, run_path = self.run_dir)
		self.assertFalse(run_info._is_sequencing_finished())

    # TODO - adapt the following tests to use the helper functions

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

