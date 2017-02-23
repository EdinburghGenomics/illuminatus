#!/usr/bin/env python3

import unittest
import sys, os

import subprocess
from tempfile import mkdtemp
from shutil import rmtree, copytree
from glob import glob

"""Here we're using a Python script to test a shell script.  The shell script calls
   various programs.  Ideally we want to have a cunning way of catching and detecting
   the calls to those programs, similar to the way that Test::Mock works.
   To this end, see the BinMocker class. I've broken this out for general use.
"""
sys.path.insert(0,'.')
from test.binmocker import BinMocker

VERBOSE = int(os.environ.get('VERBOSE', '0'))
DRIVER = os.path.abspath(os.path.dirname(__file__) + '/../driver.sh')

PROGS_TO_MOCK = """
    BCL2FASTQPreprocessor.py BCL2FASTQPostprocessor.py BCL2FASTQCleanup.py BCL2FASTQRunner.sh
    summarize_samplesheet.py rt_runticket_manager.py
""".split()

class TestDriver(unittest.TestCase):

    def setUp(self):
        """Make a shadow folder, and in it have subdirs seqdata and fastqdata and log.
           Initialize BinMocker.
           Calculate the test environment needed to run the driver.sh script.
        """
        self.temp_dir = mkdtemp()
        for d in ['seqdata', 'fastqdata', 'log']:
            os.mkdir(os.path.join(self.temp_dir, d))

        self.bm = BinMocker()
        for p in PROGS_TO_MOCK: self.bm.add_mock(p)

        # Set the driver to run in our test harness. Note I can set
        # $BIN_LOCATION to more than one path.
        self.environment = dict(
                SEQDATA_LOCATION = os.path.join(self.temp_dir, 'seqdata'),
                FASTQ_LOCATION = os.path.join(self.temp_dir, 'fastqdata'),
                BIN_LOCATION = self.bm.mock_bin_dir + ':' + os.path.dirname(DRIVER),
                LOG_DIR = os.path.join(self.temp_dir, 'log'), #this is redundant if...
                MAINLOG = "/dev/stdout",
                NO_HST_CHECK = '1',
            )

        # See the errors in all their glory
        self.maxDiff = None

    def tearDown(self):
        """Remove the shadow folder and clean up the BinMocker
        """
        rmtree(self.temp_dir)

        self.bm.cleanup()

    def bm_rundriver(self, expected_retval=0, check_stderr=True):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs DRIVER and returns STDOUT split into an array.
        """
        retval = self.bm.runscript(DRIVER, set_path=False, env=self.environment)

        #Where a file is missing it's always useful to see the error.
        #(status 127 is the standard shell return code for a command not found)
        if retval == 127 or VERBOSE:
            print("STDERR:")
            print(self.bm.last_stderr)
        if VERBOSE:
            print("STDOUT:")
            print(self.bm.last_stdout)
            print("RETVAL: %s" % retval)

        self.assertEqual(retval, expected_retval)

        #If the return val is 0 then stderr should normally be empty.
        #An exception would be if scanning one run dir fails but the
        #script continues on to other runs.
        if retval == 0 and check_stderr:
            self.assertEqual(self.bm.last_stderr, '')

        return self.bm.last_stdout.split("\n")

    def copy_run(self, run):
        """Utility function to add a run from seqdata_examples into TMP/seqdata.
           Returns the path to the run copied.
        """
        run_dir = os.path.join(os.path.dirname(__file__), 'seqdata_examples', run)

        return copytree(run_dir,
                        os.path.join(self.temp_dir, 'seqdata', run),
                        symlinks = True )

    def assertInStdout(self, *words):
        """Assert that there is at least one line in stdout containing all these strings
        """
        o_split = self.bm.last_stdout.split("\n")

        #This loop progressively prunes down the lines, until anything left
        #must have contained each word in the list.
        for w in words:
            o_split = [ l for l in o_split if w in l ]

        self.assertTrue(o_split)

    ### And the actual tests ###

    def test_nop(self):
        """With no data, nothing should happen. At all.
           The script will exit with status 1 as the glob pattern match will fail.
           Message going to STDERR should trigger an alert from CRON.
        """
        self.bm_rundriver(expected_retval=1)

        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

        self.assertTrue('no match' in self.bm.last_stderr)

    def test_no_seqdata(self):
        """If no SEQDATA_LOCATION is set, expect a fast failure.
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        self.environment['SEQDATA_LOCATION'] = 'meh'
        self.bm_rundriver(expected_retval=1)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertEqual(self.bm.last_stderr, "No such directory 'meh'\n")

        del(self.environment['SEQDATA_LOCATION'])
        self.bm_rundriver(expected_retval=1)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertTrue('SEQDATA_LOCATION: unbound variable' in self.bm.last_stderr)

    def test_new(self, test_data=None):
        """A completely new run.  This should gain a ./pipeline folder
           which puts it into status reads_incomplete.
           Also the rt_runticket_manager.py and summarize_samplesheet.py programs should
           be called but nothing else.

        """
        if not test_data:
            test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

            #We need to remove the flag file to make it look like the run is still going.
            os.system("rm " + test_data + "/RTAComplete.txt")

        self.bm_rundriver()

        #Run should be seen
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "NEW")

        #Pipeline folder should appear
        self.assertTrue(os.path.isdir(
                                os.path.join(test_data, 'pipeline') ))

        #Sample sheet should be summarized
        expected_calls = self.bm.empty_calls()
        expected_calls['rt_runticket_manager.py'] = ['-r 160606_K00166_0102_BHF22YBBXX --reply @pipeline/sample_summary.txt']
        expected_calls['summarize_samplesheet.py'] = ['']

        #But nothing else should happen
        self.assertEqual(self.bm.last_calls, expected_calls)

    def test_reads_finished(self):
        """A run ready to go through the pipeline.
             SampleSheet.csv should be converted to a symlink
             A demultiplexing folder should appear in fastqdata
             BCL2FASTQPreprocessor.py should be invoked
             The log should say "READS_FINISHED"
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        #Now we need to make the ./pipeline folder to push it out of status NEW
        os.system("mkdir -p " + test_data + "/pipeline")

        self.bm_rundriver()

        #Check samplesheet link.
        #In real operation the file will be re-fetched from the LIMS.
        self.assertEqual( os.readlink(os.path.join(test_data, "SampleSheet.csv")),
                          "SampleSheet.csv.0" )

        #Check demultiplexing folder
        fastqdir = os.path.join(self.temp_dir, "fastqdata", "160606_K00166_0102_BHF22YBBXX")
        self.assertTrue( os.path.isdir(os.path.join(fastqdir, "demultiplexing")) )

        #Check presence of 8 lock files
        self.assertEqual( 8, len( glob(os.path.join(test_data, 'pipeline', 'lane?.started')) ) )

        #Check invoking of preprocessor
        self.assertEqual( self.bm.last_calls['BCL2FASTQPreprocessor.py'][0],
                          test_data + " " + os.path.join(fastqdir, "demultiplexing") + "/"
                        )
        self.assertEqual( len(self.bm.last_calls['BCL2FASTQPreprocessor.py']), 1)

        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "READS_FINISHED")

    def test_new_and_finished(self):
        """A run which is complete which has no pipeline folder.
        """
        #At the moment, the run will be treated as new, and the summary SampleSheet will
        #be dropped into the pipeline/ directory. Only on the next iteration will the
        #pipeline actually be started.

        #Therefore this test is the same as for test_new, but without removing the
        #RTAComplete file.
        self.test_new(self.copy_run("160606_K00166_0102_BHF22YBBXX"))


    def test_in_pipeline(self):

        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        #Mark the run as started.
        os.system("mkdir -p " + test_data + "/pipeline")
        os.system("touch " + test_data + "/pipeline/lane{1..8}.started")

        self.bm_rundriver()

        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "IN_PIPELINE")

    def test_completed(self):

        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        os.system("mkdir -p " + test_data + "/pipeline")
        os.system("touch " + test_data + "/pipeline/lane{1..8}.started")
        os.system("touch " + test_data + "/pipeline/lane{1..8}.done")

        self.bm_rundriver()

        #I'm not sure if the driver should log anything for completed runs, but for now it
        #logs a message containing 'status complete'
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "status complete")

    @unittest.expectedFailure
    def test_redo(self):
        """TODO"""
        self.assertTrue(False)

if __name__ == '__main__':
    unittest.main()
