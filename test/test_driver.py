#!/usr/bin/env python3

import unittest
import sys, os, re

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

VERBOSE = os.environ.get('VERBOSE', '0') != '0'
DRIVER = os.path.abspath(os.path.dirname(__file__) + '/../driver.sh')

PROGS_TO_MOCK = """
    BCL2FASTQPreprocessor.py BCL2FASTQPostprocessor.py BCL2FASTQCleanup.py
    Snakefile.qc Snakefile.demux Snakefile.welldups
    summarize_lane_contents.py rt_runticket_manager.py upload_report.sh
""".split()

class T(unittest.TestCase):

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

        # Special mock for samplesheet fetcher. Emulates initial fetch.
        self.bm.add_mock("samplesheet_fetch.sh",
                         side_effect = "[ -e SampleSheet.csv.0 ] || (" +
                                       "mv SampleSheet.csv SampleSheet.csv.0 ;" +
                                       " ln -s SampleSheet.csv.0 SampleSheet.csv )")

        # Set the driver to run in our test harness. Note I can set
        # $BIN_LOCATION to more than one path.
        # Also we need to set VERBOSE to the driver even if it's not set for the test script.
        self.environment = dict(
                SEQDATA_LOCATION = os.path.join(self.temp_dir, 'seqdata'),
                FASTQ_LOCATION = os.path.join(self.temp_dir, 'fastqdata'),
                BIN_LOCATION = self.bm.mock_bin_dir + ':' + os.path.dirname(DRIVER),
                LOG_DIR = os.path.join(self.temp_dir, 'log'), #this is redundant if...
                MAINLOG = "/dev/stdout",
                NO_HST_CHECK = '1',
                ENVIRON_SH = '/dev/null',
                VERBOSE = '1'
            )

        # Also globally clear some environment variables that might have been set outside
        # of this script.
        for e in 'RUN_NAME_PATTERN SEQDATA_LOCATION FASTQ_LOCATION'.split():
            if e in os.environ: del(os.environ[e])

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

    def shell(self, cmd):
        """Call to os.system in 'safe mode'
        """
        status = os.system("set -euo pipefail ; " + cmd)
        if status:
            raise ChildProcessError("Exit status was %s runnign command:\n%s" % (status, cmd))

        return status

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

           Also the samplesheet_fetch.sh, rt_runticket_manager.py and summarize_lane_contents.py
           programs should be called.

           And there should be a pipeline.log in the ./pipeline folder.
        """
        if not test_data:
            test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

            #We need to remove the flag file to make it look like the run is still going.
            os.system("rm " + test_data + "/RTAComplete.txt")

        self.bm_rundriver()

        #Run should be seen
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "NEW")

        #Pipeline folder should appear
        self.assertTrue(os.path.isdir(test_data + '/pipeline'))

        #Sample sheet should be summarized
        expected_calls = self.bm.empty_calls()
        expected_calls['samplesheet_fetch.sh'] = ['']
        expected_calls['summarize_lane_contents.py'] = ['--yml pipeline/sample_summary.yml',
                                                        '--from_yml pipeline/sample_summary.yml --txt -']
        expected_calls['rt_runticket_manager.py'] = ['-r 160606_K00166_0102_BHF22YBBXX --subject new --comment @???']
        expected_calls['Snakefile.qc'] = ['-- metadata_main', '-F --config pstatus=Waiting for data -- multiqc_main']
        expected_calls['upload_report.sh'] = [self.temp_dir + '/fastqdata/160606_K00166_0102_BHF22YBBXX']

        #The call to rt_runticket_manager.py is non-deterministic, so we have to doctor it...
        self.bm.last_calls['rt_runticket_manager.py'][0] = re.sub(
                                    r'@\S+$', '@???', self.bm.last_calls['rt_runticket_manager.py'][0] )

        #But nothing else should happen
        self.assertEqual(self.bm.last_calls, expected_calls)

        #Log file should appear (here accessed via the output symlink)
        self.assertTrue(os.path.isfile(test_data + '/pipeline/output/pipeline.log') )

    def test_new_multiqc_fail(self):
        """Same as above but MultiQC fails for some reason.
           This needs to be non-fatal as we still want demultiplexing to kick in.
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")
        os.system("rm " + test_data + "/RTAComplete.txt")

        self.bm.add_mock('Snakefile.qc', fail=True)

        self.bm_rundriver()

        self.assertTrue(os.path.isdir(test_data + '/pipeline'))
        self.assertTrue(os.path.islink(test_data + '/pipeline/output'))
        self.assertTrue(os.path.islink(test_data + '/pipeline/output/seqdata'))

        self.assertEqual( len(self.bm.last_calls['rt_runticket_manager.py']), 1 )
        self.assertEqual( self.bm.last_calls['upload_report.sh'], [] )
        self.assertFalse( os.path.exists(test_data + '/pipeline/failed') )

    def test_read1_multiqc_fail(self):
        """A failure to run interop/multiqc when finishing up with read1 processing should
           not cause the pipeline to jam in eg. read1_processing state.
        """
        test_data = self.copy_run("160603_M01270_0196_000000000-AKGDE")

        # For this, we want summarize_lane_contents.py to actually make a file
        self.bm.add_mock("summarize_lane_contents.py",
                         side_effect = "echo TEST > pipeline/sample_summary.yml")

        # Run the driver (first with everything OK)
        self.bm_rundriver()

        # Test that rt_runticket_manager.py was called and read1.done appeared.
        self.assertEqual(len(self.bm.last_calls['rt_runticket_manager.py']), 1)
        self.assertEqual(len(self.bm.last_calls['Snakefile.qc']), 3)
        self.assertTrue(os.path.isfile( test_data + "/pipeline/read1.done" ))
        self.assertTrue(os.path.isfile( test_data + "/pipeline/sample_summary.yml" ))

        # Look for the success note in the log
        self.assertInStdout("Completed read1 processing")

        # Make it so Snakefile.qc and rt_runticket_manager.py fails, and remove the output files, and go once more.
        self.bm.add_mock('rt_runticket_manager.py', fail=True)
        self.bm.add_mock('Snakefile.qc', fail=True)
        os.system("rm " + test_data + "/pipeline/read1.done")
        os.system("rm " + test_data + "/pipeline/sample_summary.yml")
        self.bm_rundriver()

        # Test (again) that despite the failure read1.done still appeared
        self.assertEqual(len(self.bm.last_calls['rt_runticket_manager.py']), 1)
        self.assertEqual(len(self.bm.last_calls['Snakefile.qc']), 3)
        self.assertTrue(os.path.isfile( test_data + "/pipeline/read1.done" ))

        # Possibly driver.sh should remove this if RT communication fails??
        # No, since we are no longer worrying about sample sheet updates on read1
        # processing because there will always be a summary sent with the final e-mail.
        self.assertTrue(os.path.isfile( test_data + "/pipeline/sample_summary.yml" ))

        # Look for the failure note in the log
        self.assertInStdout("errors in read1 processing")

    def test_reads_finished(self):
        """A run ready to go through the main pipeline (read1 + demux).
             SampleSheet.csv should be converted to a symlink
             A demultiplexing folder should appear in fastqdata
             BCL2FASTQPreprocessor.py should be invoked
             The log should say "READS_FINISHED"
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        #Now we need to make the ./pipeline folder to push it out of status NEW.
        self.shell("mkdir -p " + test_data + "/pipeline")

        #Run the driver once to do the read1 processing (a no-op due to the mocks)
        self.bm_rundriver()

        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "READ1_FINISHED")
        # 'Snakefile.qc -- interop' gets called twice. It's a bit scrappy but shouldn't be
        # a problem as Snakemake will quickly determine that the files are up-to-date.
        self.assertEqual( len(self.bm.last_calls['Snakefile.qc']), 2 + 1 )
        self.assertTrue(os.path.isfile( test_data + "/pipeline/read1.done" ))

        #The second one will actually demultiplex.
        self.bm_rundriver()

        #Check samplesheet link.
        #In real operation the file will be re-fetched from the LIMS.
        self.assertEqual( os.readlink(os.path.join(test_data, "SampleSheet.csv")),
                          "SampleSheet.csv.0" )

        #Check demultiplexing folder
        fastqdir = os.path.join(self.temp_dir, "fastqdata", "160606_K00166_0102_BHF22YBBXX")
        self.assertTrue( os.path.isdir(os.path.join(fastqdir, "demultiplexing")) )

        #Check presence of 8 .done files
        self.assertEqual( 8, len( glob(os.path.join(test_data, 'pipeline', 'lane?.done')) ) )

        #Check invoking of Snakefile.demux (in the sedata dir)
        self.assertEqual( self.bm.last_calls['Snakefile.demux'][0],
                          '--config lanes=1 2 3 4 5 6 7 8 rundir={}'.format(test_data)
                        )

        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "READS_FINISHED")

    def test_demux_error(self):
        """Simulate an error in BCL2FASTQPreprocessor.py. This should lead to the
           run going into an error state and the message 'FAIL processing $RUNID'
           appearing in the log.
        """
        # Start the same as test_reads_finished...
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")
        self.shell("mkdir -p " + test_data + "/pipeline")
        self.shell("touch " + test_data + "/pipeline/read1.started")

        self.bm.add_mock('Snakefile.demux', fail=True)

        self.bm_rundriver()

        # We said read1 was started so we should be in this state:
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "IN_READ1_QC_READS_FINISHED")

        # I still expect to see the demultiplexing folder and 8 lock files,
        # as these are not removed on failure.
        fastqdir = os.path.join(self.temp_dir, "fastqdata", "160606_K00166_0102_BHF22YBBXX")
        self.assertTrue( os.path.isdir(os.path.join(fastqdir, "demultiplexing")) )
        self.assertEqual( 8, len( glob(os.path.join(test_data, 'pipeline/lane?.started')) ) )

        # Look for evidence of clean failure, report to RT, etc.
        self.assertTrue( os.path.exists(os.path.join(test_data, 'pipeline', 'failed')) )
        self.assertEqual( self.bm.last_calls['rt_runticket_manager.py'][-1],
                          "-r 160606_K00166_0102_BHF22YBBXX --subject failed --reply " +
                          "Demultiplexing failed. See log in " + fastqdir + "/pipeline.log"
                        )
        self.assertInStdout("FAIL Demultiplexing 160606_K00166_0102_BHF22YBBXX")

    def test_new_and_finished(self):
        """A run which is complete which has no pipeline folder.
        """
        # At the moment, the run will be treated as new, and the summary SampleSheet will
        # be dropped into the pipeline/ directory. Only on the next iteration will the
        # pipeline actually be started.

        # Therefore this test is the same as for test_new, but without removing the
        # RTAComplete file.
        self.test_new(self.copy_run("160606_K00166_0102_BHF22YBBXX"))


    def test_in_pipeline(self):

        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        # Mark the run as started, and let's say we're processing read1
        self.shell("mkdir -p " + test_data + "/pipeline")
        self.shell("touch " + test_data + "/pipeline/read1.started")
        self.shell("touch " + test_data + "/pipeline/lane{1..8}.started")

        self.bm_rundriver()
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "IN_DEMULTIPLEXING")

        # Finishing read1 shouldn't change matters
        self.shell("touch " + test_data + "/pipeline/read1.done")

        self.bm_rundriver()
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "IN_DEMULTIPLEXING")

    def test_completed(self):

        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        self.shell("mkdir -p " + test_data + "/pipeline")
        self.shell("touch " + test_data + "/pipeline/lane{1..8}.started")
        self.shell("touch " + test_data + "/pipeline/lane{1..8}.done")
        self.shell("touch " + test_data + "/pipeline/read1.done")
        self.shell("touch " + test_data + "/pipeline/qc.done")

        self.bm_rundriver()

        #Normally the driver should not log anything for completed runs, but in debug
        #mode it logs a message containing 'status=complete'
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "status=complete")

    def test_redo(self):
        """A run which was partly completed but we want to redo lanes 1 and 2
           Lane 2 will be marked as done but lane 1 will not.
        """

        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")
        fastqdir = os.path.join(self.temp_dir, "fastqdata", "160606_K00166_0102_BHF22YBBXX")

        self.shell("mkdir -p " + test_data + "/pipeline")
        self.shell("touch " + test_data + "/pipeline/read1.done")
        self.shell("touch " + test_data + "/pipeline/lane{1..8}.started")
        self.shell("touch " + test_data + "/pipeline/lane{2..8}.done")

        # Without this failed flag, the RunStatus will be in_demultiplexing.
        self.shell("touch " + test_data + "/pipeline/failed")
        self.shell("touch " + test_data + "/pipeline/lane{1,2}.redo")
        self.shell("mkdir -p " + fastqdir + "/demultiplexing")

        # This should suppresss sending a new report to RT, since there will
        # already appear to be an up-to-date samplesheet plus a summary.
        self.bm.runscript("cd " + test_data + "; samplesheet_fetch.sh")
        self.shell("touch " + test_data + "/pipeline/sample_summary.yml")

        # This should do many things...
        self.bm_rundriver()

        # The driver should spot that the run needed a REDO
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "status=redo")

        # It should have called for a cleanup on lanes 1 and 2
        self.assertEqual( self.bm.last_calls['BCL2FASTQCleanup.py'],
                          [fastqdir + " 1 2"]
                        )

        # It should have called Snakefile.demux
        self.assertEqual( self.bm.last_calls['Snakefile.demux'],
                          ["--config lanes=1 2 rundir=" + test_data ]
                        )

        # It should have removed the .done, .started and .redo files, then
        # recreated the .done files for these two lanes.
        # The .started files for the other lanes should also be removed (in general
        # we wouldn't expect to find both a .started and a .done)
        self.assertEqual([os.path.exists(test_data + "/pipeline/" + f) for f in [
                            'lane1.started', 'lane1.done', 'lane1.redo',
                            'lane2.started', 'lane2.done', 'lane2.redo',
                            'lane3.started', 'lane3.done', 'lane3.redo' ]
                         ], [False,           True,         False,
                             False,           True,         False,
                             False,           True,         False ])

        # Check that summarize_lane_contents.py really wasn't called
        #self.assertEqual( self.bm.last_calls['summarize_lane_contents.py'], [] )
        #
        # Nope - I'm now deleting the summary on redo because the links might have changed.
        # And since we now send the summary each time anyway it doesn't make sense to bother
        # detecting if the sample sheet changed or not.
        # So check the summary is re-made and then read back to make the e-mail:
        self.assertEqual( self.bm.last_calls['summarize_lane_contents.py'], [
                                '--yml pipeline/sample_summary.yml',
                                '--from_yml pipeline/sample_summary.yml --txt -' ] )

        # And two notes should go to RT - a reply about the redo starting and a comment about the success.
        # The first call to rt_runticket_manager.py is non-deterministic, so we have to doctor it...
        self.bm.last_calls['rt_runticket_manager.py'][0] = re.sub(
                                    r'@\S+$', '@???', self.bm.last_calls['rt_runticket_manager.py'][0] )
        self.assertEqual( self.bm.last_calls['rt_runticket_manager.py'],
                          ["-r 160606_K00166_0102_BHF22YBBXX --subject redo lanes 1 2 --reply @???",

                           "-r 160606_K00166_0102_BHF22YBBXX --subject re-demultiplexed" + \
                           " --comment Re-Demultiplexing of lanes 1 2 completed"] )

    def test_redo_fail_cleanup(self):
        """If BCL2FASTQCleanup.py fails then it should stop processing the run, not continuing
           to run Snakefile.demux etc.
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")
        fastqdir = os.path.join(self.temp_dir, "fastqdata", "160606_K00166_0102_BHF22YBBXX")

        self.shell("mkdir -p " + test_data + "/pipeline")
        self.shell("touch " + test_data + "/pipeline/read1.done")
        self.shell("touch " + test_data + "/pipeline/lane{1..8}.started")
        self.shell("touch " + test_data + "/pipeline/lane{2..8}.done")

        # Without this failed flag, the RunStatus will be in_demultiplexing.
        self.shell("touch " + test_data + "/pipeline/failed")
        self.shell("touch " + test_data + "/pipeline/lane{1,2}.redo")
        self.shell("mkdir -p " + fastqdir + "/demultiplexing")

        # This should suppresss sending a new report to RT, since there will
        # already appear to be an up-to-date samplesheet plus a summary.
        self.bm.runscript("cd " + test_data + "; samplesheet_fetch.sh")
        self.shell("touch " + test_data + "/pipeline/sample_summary.yml")

        # Now ensure the cleanup fails.
        self.bm.add_mock('BCL2FASTQCleanup.py', fail=True)

        # This should do many things...
        self.bm_rundriver()

        # The driver should spot that the run needed a REDO
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "status=redo")

        # It should have called for a cleanup on lanes 1 and 2
        self.assertEqual( self.bm.last_calls['BCL2FASTQCleanup.py'],
                          [fastqdir + " 1 2"]
                        )

        # As this fails, it should should NOT have called Snakefile.demux or
        # indeed Snakefile.qc
        self.assertEqual( self.bm.last_calls['Snakefile.demux'], [] )
        self.assertEqual( self.bm.last_calls['Snakefile.qc'], [] )

        # It should have removed the .done, .started and .redo files, then logged the
        # failure.
        self.assertEqual([os.path.exists(test_data + "/pipeline/" + f) for f in [
                            'lane1.started', 'lane1.done', 'lane1.redo',
                            'lane2.started', 'lane2.done', 'lane2.redo',
                            'lane3.started', 'lane3.done', 'lane3.redo', 'failed' ]
                         ], [True,            False,        False,
                             True,            False,        False,
                             False,           True,         False,       True ])

        # Check that summarize_lane_contents.py really wasn't called
        self.assertEqual( self.bm.last_calls['summarize_lane_contents.py'], [] )

        # And a note about the failure should go to RT
        # Since the cleanup runs before the call to run_multiqc we won't get the redo notification to RT at all.
        self.assertEqual( self.bm.last_calls['rt_runticket_manager.py'],
                          ["-r 160606_K00166_0102_BHF22YBBXX --subject failed --reply Cleanup_for_Re-demultiplexing failed." + \
                           " See log in " + fastqdir + "/pipeline.log" ] )

if __name__ == '__main__':
    unittest.main()
