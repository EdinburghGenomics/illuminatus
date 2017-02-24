#!/usr/bin/env python3

import sys, os

import subprocess
from tempfile import mkdtemp
from shutil import rmtree, copytree
from glob import glob

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

        self._make_mockscript("_MOCK", 0)
        self._make_mockscript("_MOCKF", 1)

        self.mocks = set()
        for m in mocks:
            self.add_mock(m)

        self.last_calls = None
        self.last_stderr = None
        self.last_stdout = None

    def _make_mockscript(self, mockname, retcode, side_effect="#NOP"):
        """Internal function for making mock scripts.
        """

        mockscript = '''
            #!/bin/sh
            {side_effect}
            echo "`basename $0` $@" >> "`dirname $0`"/_MOCKCALLS ; exit {retcode}
        '''.format(**locals())

        with open(os.path.join(self.mock_bin_dir, mockname), 'w') as fh:
            print(mockscript.strip(), file=fh)

            # copy R bits to X to achieve comod +x
            mode = os.stat(fh.fileno()).st_mode
            os.chmod(fh.fileno(), mode | (mode & 0o444) >> 2)


    def add_mock(self, mock, fail=False, side_effect=None):
        """Symlink the named script so that it will get called in
           place of the real version.
        """
        symlink = os.path.join(self.mock_bin_dir, mock)

        if side_effect:
            #We need a special script then
            target = "_MOCK_" + mock
            self._make_mockscript(target, 1 if fail else 0, side_effect)
        else:
            target = "_MOCKF" if fail else "_MOCK"

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
           can alternatively specify set_path=False in which case you take
           responsibility for adding bm.mock_bin_dir to the PATH.
        """
        #Cleanup _MOCKCALLS if found
        calls_file = os.path.join(self.mock_bin_dir, "_MOCKCALLS")
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

        #Fish the MOCK calls out of _MOCKCALLS
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

