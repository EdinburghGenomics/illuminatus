#!/usr/bin/env python3

"""BinMocker - a hack for testing shell scripts in Python"""

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
        self._bash_env = None
        for m in mocks:
            self.add_mock(m)

        self.last_calls = None
        self.last_stderr = None
        self.last_stdout = None

    def _make_mockscript(self, mockname, retcode, side_effect="#NOP"):
        """Internal function for making mock scripts.
        """

        # To make the saving of args robust I had this idea:
        # for x in "$@" ; do _fs+=(%q) ; done
        # printf "%q %d ${_fs[*]}\n" "$0" "$#" "$@"
        # But using zeros seems better.

        mockscript = r'''
            #!/bin/bash
            {side_effect}
            _fs='%s\0%d\0' ; for x in "$@" ; do _fs+='%s\0' ; done ; _fs+='\n'
            printf "$_fs" "$(basename "$0")" "$#" "$@" >> "$(dirname "$0")"/_MOCKCALLS
            exit {retcode}
        '''.format(**locals())

        with open(os.path.join(self.mock_bin_dir, mockname), 'w') as fh:
            print(mockscript.strip(), file=fh)

            # copy R bits to X to achieve chmod +x
            mode = os.stat(fh.fileno()).st_mode
            os.chmod(fh.fileno(), mode | (mode & 0o444) >> 2)

    def _add_mockfunc(self, funcname, retcode, side_effect="#NOP"):
        """Internal function for writing mock functions.
           Note these will only apply to scripts that explicitly use #!/bin/bash
           as the interpreter, not #!/bin/sh or any other way that commands are
           called indirectly, like 'env /bin/true ...'.
        """
        calls_file = os.path.join(self.mock_bin_dir, "_MOCKCALLS")

        mockfunc = r'''
            {funcname}(){{
            {side_effect}
            local _fs
            _fs='%s\0%d\0' ; for x in "$@" ; do _fs+='%s\0' ; done ; _fs+='\n'
            printf "$_fs" '{funcname}' "$#" "$@" >> "$(dirname "$BASH_SOURCE")"/_MOCKCALLS
            return {retcode} ; }}
        '''.format(**locals())

        with open(os.path.join(self.mock_bin_dir, '_BASHENV'), 'a') as fh:
            print(mockfunc.strip(), file=fh)

        self._bash_env = os.path.join(self.mock_bin_dir, "_BASHENV")


    def add_mock(self, mock, fail=False, side_effect=None):
        """Symlink the named script so that it will get called in
           place of the real version.
           Except if mock contains a / character - then we need to use
           functions instead.
        """
        if '/' in mock:
            #We can still mock these by defining BASH functions.
            self._add_mockfunc(mock, 1 if fail else 0, side_effect)

        else:

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

            if self._bash_env:
                # Note - interactive scripts shouldn't normally depend on BASH_ENV,
                # so complain if I'm clobbering it. Ditto for ENV.
                if full_env.get('BASH_ENV'):
                    raise RuntimeError("BASH_ENV was already set")

                full_env['BASH_ENV'] = self._bash_env

        p = subprocess.Popen(cmd, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE,
                             universal_newlines = True,
                             env = full_env,
                             executable = "/bin/bash",
                             close_fds=True)

        self.last_stdout, self.last_stderr = p.communicate()

        #Fish the MOCK calls out of _MOCKCALLS
        calls = self.empty_calls()
        try:
            with open(calls_file, newline='\n') as fh:
                for l in fh:
                    # Each line is \0 delimited
                    mock_name, mock_argc, mock_argv = l.split('\0', 2)
                    while mock_argv.count('\0') < int(mock_argc):
                        # Must be an embedded newline; pull the next line
                        mock_argv += next(fh)
                    # The line should end in \0 so discard the last ''
                    mock_args = mock_argv.rstrip('\n').split('\0')[:-1]
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

