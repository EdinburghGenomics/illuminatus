#!/usr/bin/env python3

"""Create and manipulate sandboxes for unit tests"""
import os, sys, re

import datetime
from tempfile import mkdtemp
from shutil import rmtree, copytree
from fnmatch import fnmatch

class TestSandbox:
    """A class that manages a sandbox directory and helps you to
       manipulate files in that directory with specific timestamps.
    """
    def __init__(self, copydir=None, follow_symlinks=False):
        """Create a sandbox and fill it with the contents of a given
           directory.
        """
        # Make a temporary directory.
        self.sandbox = self._sandbox = mkdtemp()

        # Just to be sure, this should be an absolute path
        assert self._sandbox.startswith("/")

        # Fill it with stuff
        if copydir:
            self.sandbox = copytree( copydir,
                                     os.path.join( self._sandbox, os.path.basename(copydir) ),
                                     symlinks = not follow_symlinks )

    def cleanup(self):
        """Remove the sandbox. Calling this twice will raise an exception.
        """
        rmtree(self._sandbox)
        self.sandbox = self._sandbox = None

    def touch(self, path, hours_age=0, recursive=False):
        """Update the times on a file or directory. No files will be created.
        """
        modtime = (datetime.datetime.now() - datetime.timedelta(hours=hours_age)).timestamp()

        if not recursive:
            # The easy bit...
            os.utime(os.path.join(self.sandbox, path), times=(modtime, modtime), follow_symlinks=False)
        else:
            # Now for recursion. This will only work if path is a dir.
            # A little callback to ensure exceptions are not swallowed:
            def _raise(e): raise
            for root, dirs, files in os.walk( os.path.join(self.sandbox, path),
                                              topdown = False,
                                              onerror = _raise ):
                for f in files:
                    os.utime(os.path.join(root, f), times=(modtime, modtime), follow_symlinks=False)
                os.utime(root, times=(modtime, modtime), follow_symlinks=False)

    def make(self, filename, hours_age=0, content=None):
        """Make a new file, and, if necessary, all the containing directories in
           self.sandbox. If content is not None, print the content to the file.
           Everything created will get a timestamp hours_age in the past.
           Adding a file or subdirectory to a directory will not affect the mtime of the containing
           directory.
        """
        modtime = (datetime.datetime.now() - datetime.timedelta(hours=hours_age)).timestamp()

        dirname = self.sandbox
        dirtimes = dict()

        # Make the directories
        for fp in filename.split('/')[:-1]:
            if not fp:
                continue
            dirname = os.path.join(dirname, fp)
            if not os.path.isdir(dirname):
                os.mkdir(dirname)
                dirtimes[dirname] = modtime
            else:
                # We may have to restore this if we make something in here
                dirtimes[dirname] = os.stat(dirname).st_mtime

        # Make the final file, assuming there is one
        basename = filename.split('/')[-1]
        if basename:
            with open(os.path.join(dirname, basename), 'x') as fh:
                if content is not None:
                    print(content, file=fh)
            os.utime(os.path.join(dirname, basename), times=(modtime, modtime))

        # Now go back through the directories fixing up the mtimes (strictly speaking the ordering
        # is not necessary but we may as well be orderly)
        for d in sorted(dirtimes, key=lambda s: len(s), reverse=False):
            os.utime(d, times=(dirtimes[d], dirtimes[d]))

    def link(self, src, dest, hours_age=0):
        """Wraps os.symlink within self.sandbox and sets the age of the link.
           If the target dir does not exist, it will be created, and the the mtime will be
           preserved as above.
        """
        modtime = (datetime.datetime.now() - datetime.timedelta(hours=hours_age)).timestamp()

        dirname = self.sandbox
        dirtimes = dict()
        # This doens't work.
        assert not dest.endswith('/')

        # Make the directories (copy-paste alert!)
        for fp in dest.split('/')[:-1]:
            if not fp:
                continue
            dirname = os.path.join(dirname, fp)
            if not os.path.isdir(dirname):
                os.mkdir(dirname)
                dirtimes[dirname] = modtime
            else:
                # We may have to restore this if we make something in here
                dirtimes[dirname] = os.stat(dirname).st_mtime

        # Make the link,
        # Since self.sandbox is an absolute path we don't need to worry about
        # using os.path.relpath() to emulate "ln -sr"
        os.symlink(os.path.join(self.sandbox, src), os.path.join(self.sandbox, dest))
        os.utime(os.path.join(self.sandbox, dest), times=(modtime, modtime),  follow_symlinks=False)

        # Now go back through the directories fixing up the mtimes (strictly speaking the ordering
        # is not necessary but we may as well be orderly)
        for d in sorted(dirtimes, key=lambda s: len(s), reverse=False):
            os.utime(d, times=(dirtimes[d], dirtimes[d]))


    def lsdir(self, adir, glob="*"):
        return sorted(f for f in os.listdir(os.path.join(self.sandbox, adir)) if fnmatch(f, glob))
