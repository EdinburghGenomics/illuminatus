Illuminatus uses various tools to process the sequence files. Some are called directly
and others are called indirectly as part of other tools. Aside from those contained
directly within the Illuminatus codebase and those managed under the Python3 VEnv,
everything called by Illuminatus should be collected here.

Every executable in this directory should be either a link to a tool installed under
/lustre/software or else a thin wrapper shell script that references the tool. The
link or reference should be to the specific numbered version, never to the 'current'
symlink or to whatever is sitting under /lustre/software/bin.

The upshot of this rule is that we can tinker with the 'current' symlinks and the contents
of '/lustre/software/bin' without breaking the pipeline. We can also see exactly what the
pipeline is using by just examining this directory. I'm in two minds if this directory should
continue to sit in /lustre/software or should be kept in the Illuminatus GIT repository
with the rest of the code.

If you want to test with a new version of anything you should copy the *whole* directory and
set $TOOLBOX in your test environment (eg. in environ.sh). Then when you are happy you can
change the production version.
