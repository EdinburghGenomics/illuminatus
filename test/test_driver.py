#!/usr/bin/env python3

import unittest
import sys, os, glob

import subprocess
from tempfile import mkdtemp
from shutil import rmtree

"""Here we're using a Python script to test a shell script.  The shell script calls
   various programs.  Ideally we want to have a cunning way of catching and detecting
   the calls to those programs, similar to the way that Test::Mock works.
   And I thinkl I know how to do it.
"""

sys.path.insert(0,'.')
TEST_DATA = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')

class TestDriver(unittest.TestCase):

    def setUp( self ):
        os.system("mkdir -p " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/")
        os.system("rm " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/*")

    def test_reads_finished( self ):
        os.system("touch " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/")
        assert os.system("/home/mberinsk/workspace/illuminatus/bin/driver.sh | grep 160606_K00166_0102_BHF22YBBXX | grep READS_FINISHED") == 0

    def test_in_pipeline( self ):
        os.system("touch " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/lane{1..8}.started")
        assert os.system("/home/mberinsk/workspace/illuminatus/bin/driver.sh | grep 160606_K00166_0102_BHF22YBBXX | grep IN_PIPELINE" ) == 0

    def test_completed( self ):
        os.system("touch " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/lane{1..8}.done")
        assert os.system("/home/mberinsk/workspace/illuminatus/bin/driver.sh | grep 160606_K00166_0102_BHF22YBBXX | grep COMPLETE" ) == 0

class TestDriverNEW(unittest.TestCase):

    def setUp( self ):
        os.system("rm " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/*")
        os.system("rmdir " + TEST_DATA + "/160606_K00166_0102_BHF22YBBXX/pipeline/")

    def test_new( self ):
        assert os.system("/home/mberinsk/workspace/illuminatus/bin/driver.sh | grep 160606_K00166_0102_BHF22YBBXX | grep NEW") == 0

class TestBinMocker(unittest.TestCase):
    """Internal testing for BinMocker helper
    """
    def test_bin_mocker(self):
        

class BinMocker:
    """A helper class that provides a way to replace tools with dummy
       calls and then summarize what was called.
       This won't be anywhere near as robust/comprehensive as Test::Mock but it will do.

         with BinMocker('mycmd') as bm:
            bm.runscript('foo.sh')

            #Check that foo.sh called mycmd once.
            assert len(bm.last_calls['mycmd']) == 2
    """

    def __init__(*mocks):
        self.mock_bin_dir = mkdtemp()

        mockscript = '''
            #!/bin/sh
            echo "###_MOCK### $0 $@" >&2
        '''

        mockscript_fail = '''
            #!/bin/sh
            echo "###_MOCK### $0 $@" >&2 ; exit 1
        '''

        with open(os.path.join(self.mock_bin_dir + "_MOCK")) as fh:
            print(mockscript.strip(), file=fh)

            # copy R bits to X to achieve comod +x
            mode = os.stat(fh).st_mode
            os.chmod(fh, mode | (mode & 0o444) >> 2)

        with open(os.path.join(self.mock_bin_dir + "_MOCK_F")) as fh:
            print(mockscript_fail.strip(), file=fh)

            # copy R bits to X to achieve comod +x
            mode = os.stat(fh).st_mode
            os.chmod(fh, mode | (mode & 0o444) >> 2)

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
        target = "_MOCK_F" if fail else "_MOCK"

        os.symlink(target, os.path.join(self.mock_bin_dir, mock))

        self.mocks.add(mock)

    def cleanup():
        """Clean up
        """
        rmtree(self.mock_bin_dir)
        self.mock_bin_dir = None

    def runscript(cmd, set_path=True, env=None):
        """Runs the specified command, which may contain shell syntax,
           and captures the output and the commands that were invoked.
        """
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

        stdout, stderr = p.communicate()

        #Fish the MOCK stuff out of stderr
        calls = [ [] for m in self.mocks ]
        new_stderr = []
        prefix = ''
        for l in stderr.split("\n"):
            if '###_MOCK### ' in l:
                pre_bit, mock_bit = l.split('###_MOCK### ')
                #This only matters if the script printed something without a trailing \n
                prefix = prefix + pre_bit

                mock_name, mock_args = mock_bit.split(' ', 1)
                calls[mock_name].append(mock_args)
            else:
                new_stderr.append(prefix + l)
                prefix = ''
        if prefix:
            new_stderr.append(prefix)

        #Stash the calls and stdout/stderr
        self.last_calls = calls
        self.last_stderr = new_stderr
        self.last_stdout = stdout.split("\n")

        #Return whatever the process returned
        return p.returncode

    #Allow the class to be used in a "with" construct.
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        cleanup()

if __name__ == '__main__':
    unittest.main()

