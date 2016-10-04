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
   To this end, see the BinMocker class. I'll probably break this out for general use.
"""

sys.path.insert(0,'.')
VERBOSE = False
DRIVER = os.path.abspath(os.path.dirname(__file__) + '/../driver.sh')

PROGS_TO_MOCK = """
    BCL2FASTQPreprocessor.py BCL2FASTQPostprocessor.py BCL2FASTQCleanup.py BCL2FASTQRunner.sh
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

    def bm_rundriver(self, expected_retval=0):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs DRIVER and returns STDOUT split into an array.
        """
        retval = self.bm.runscript(DRIVER, set_path=False, env=self.environment)

        #Where a file is missing it's always useful to see the error.
        if retval == 127 or VERBOSE:
            print("STDERR:")
            print(self.bm.last_stderr)
        if VERBOSE:
            print("STDOUT:")
            print(self.bm.last_stdout)

        self.assertEqual(retval, expected_retval)

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

    def test_nop( self ):
        """With no data, nothing should happen. At all.
        """
        self.bm_rundriver()

        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

    def test_new( self ):
        """A completely new run.  This should gain a ./pipeline folder
           which puts it into status reads_incomplete.
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        #We need to remove the flag file to make it look like the run is still going.
        os.system("rm " + test_data + "/RTAComplete.txt")

        self.bm_rundriver()

        #Run should be seen
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "NEW")

        #Pipeline folder should appear
        self.assertTrue(os.path.isdir(
                                os.path.join(test_data, 'pipeline') ))

        #But nothing else should happen
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

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
        #FIXME - or should the samplehseet be re-fetched from the LIMS?
        self.assertEqual( os.readlink(os.path.join(test_data, "SampleSheet.csv")),
                          "SampleSheet.csv.0" )

        #Check demultiplexing folder
        fastqdir = os.path.join(self.temp_dir, "fastqdata", "160606_K00166_0102_BHF22YBBXX")
        self.assertTrue( os.path.isdir(os.path.join(fastqdir, "demultiplexing")) )

        #Check presence of 8 lock files
        self.assertEqual( 8, len( glob(os.path.join(test_data, 'pipeline', 'lane?.started')) ) )

        #Check invoking of preprocessor
        self.assertEqual( self.bm.last_calls['BCL2FASTQPreprocessor.py'],
                          [ test_data + " " + os.path.join(fastqdir, "demultiplexing") + "/" ]
                        )

        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "READS_FINISHED")

    def test_new_and_finished(self):
        """A run which is complete which has no pipeline folder.
        """
        test_data = self.copy_run("160606_K00166_0102_BHF22YBBXX")

        #At the moment, the run will be treated as new, and only on the next iteration will the
        #pipeline be started.  I'm not sude if this is the desired behaviour or not??

        self.bm_rundriver()

        # Copied from test_new...

        #Run should be seen
        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "NEW")

        #Pipeline folder should appear
        self.assertTrue(os.path.isdir(
                                os.path.join(test_data, 'pipeline') ))

        #But nothing else should happen
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

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

        self.assertInStdout("160606_K00166_0102_BHF22YBBXX", "COMPLETE")

    @unittest.expectedFailure
    def test_redo(self):
        """TODO"""
        self.assertTrue(False)

class TestBinMocker(unittest.TestCase):
    """Internal testing for BinMocker helper
    """
    def test_bin_mocker(self):
        with BinMocker('foo', 'bad') as bm:
            bm.add_mock('bad', fail=True)

            res1 = bm.runscript('true')
            self.assertEqual(res1, 0)
            self.assertEqual(bm.last_stdout, '')
            self.assertEqual(bm.last_stderr, '')
            self.assertEqual(bm.last_calls, bm.empty_calls())
            self.assertEqual(bm.last_calls, dict(foo=[], bad=[]))

            #Now something that actually calls things
            res2 = bm.runscript('echo 123 ; foo foo args ; echo 456 ; ( echo 888 >&2 ) ; bad dog ; bad doggy')
            self.assertEqual(res2, 1)
            self.assertEqual(bm.last_stdout.rstrip().split('\n'), ['123', '456'])
            self.assertEqual(bm.last_stderr.rstrip().split('\n'), ['888'])
            self.assertEqual(bm.last_calls['foo'], ["foo args"])
            self.assertEqual(bm.last_calls['bad'], ["dog", "doggy"])

            #Test that everything resets properly
            res3 = bm.runscript('true')
            self.assertEqual(res3, 0)
            self.assertEqual(bm.last_stdout, '')
            self.assertEqual(bm.last_stderr, '')
            self.assertEqual(bm.last_calls, dict(foo=[], bad=[]))

class BinMocker:
    """A helper class that provides a way to replace tools with dummy
       calls and then summarize what was called.
       This won't be anywhere near as robust/comprehensive as Test::Mock but it will do.

         with BinMocker('mycmd') as bm:
            bm.runscript('foo.sh')

            #Check that foo.sh called mycmd once.
            assert len(bm.last_calls['mycmd']) == 2
    """

    def __init__(self, *mocks):
        self.mock_bin_dir = mkdtemp()

        mockscript = '''
            #!/bin/sh
            echo "`basename $0` $@" >> "`dirname $0`"/_MOCK_CALLS
        '''

        mockscript_fail = '''
            #!/bin/sh
            echo "`basename $0` $@" >> "`dirname $0`"/_MOCK_CALLS ; exit 1
        '''

        with open(os.path.join(self.mock_bin_dir, "_MOCK"), 'w') as fh:
            print(mockscript.strip(), file=fh)

            # copy R bits to X to achieve comod +x
            mode = os.stat(fh.fileno()).st_mode
            os.chmod(fh.fileno(), mode | (mode & 0o444) >> 2)

        with open(os.path.join(self.mock_bin_dir, "_MOCK_F"), 'w') as fh:
            print(mockscript_fail.strip(), file=fh)

            # copy R bits to X to achieve comod +x
            mode = os.stat(fh.fileno()).st_mode
            os.chmod(fh.fileno(), mode | (mode & 0o444) >> 2)

        self.mocks = set()
        for m in mocks:
            self.add_mock(m)

        self.last_calls = None
        self.last_stderr = None
        self.last_stdout = None

    def add_mock(self, mock, fail=False):
        """Symlink the named script so that it will get called in
           place of the real version.
        """
        symlink = os.path.join(self.mock_bin_dir, mock)
        target = "_MOCK_F" if fail else "_MOCK"

        #If the link already exists, remove it
        try:
            os.unlink(symlink)
        except FileNotFoundError:
            pass

        os.symlink(target, symlink)

        self.mocks.add(mock)

    def cleanup(self):
        """Clean up
        """
        rmtree(self.mock_bin_dir)
        self.mock_bin_dir = None

    def runscript(self, cmd, set_path=True, env=None):
        """Runs the specified command, which may contain shell syntax,
           and captures the output and the commands that were invoked.
           By default, the mock scripts will be prepended to the PATH, but you
           can alternatively modify the environment explicity.
        """
        #Cleanup _MOCK_CALLS if found
        calls_file = os.path.join(self.mock_bin_dir, "_MOCK_CALLS")
        try:
            os.unlink(calls_file)
        except FileNotFoundError:
            pass

        full_env = None
        if env:
            full_env = os.environ.copy()
            full_env.update(env)

        if set_path:
            full_env = full_env or os.environ.copy()
            if full_env.get('PATH'):
                full_env['PATH'] = os.path.abspath(self.mock_bin_dir) + ':' + full_env['PATH']
            else:
                full_env['PATH'] = os.path.abspath(self.mock_bin_dir)

        p = subprocess.Popen(cmd, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE,
                             universal_newlines = True,
                             env = full_env,
                             close_fds=True)

        self.last_stdout, self.last_stderr = p.communicate()

        #Fish the MOCK calls out of _MOCK_CALLS
        calls = self.empty_calls()
        try:
            with open(calls_file) as fh:
                for l in fh:
                    mock_name, mock_args = l.rstrip('\n').split(' ', 1)
                    calls[mock_name].append(mock_args)
        except FileNotFoundError:
            #So, nothing ran
            pass

        self.last_calls = calls

        #Return whatever the process returned
        return p.returncode

    def empty_calls(self):
        """Get the baseline dict of calls. Useful for tests to assert that
             bm.last_calls == bm.empty_calls()
           ie. nothing happened.
        """
        return { m : [] for m in self.mocks }

    #Allow the class to be used in a "with" construct, though
    #in a TestCase you probably want to use setup/teardown.
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.cleanup()

if __name__ == '__main__':
    unittest.main()

