#!/bin/bash

# When running the tests, we need to ensure Python picks up the right environment.
# For this reason ,it's worth having a test wrapper.

# Note - at present the unit tests will only run fully when using the system Python,
# because the VirtualEnv Python can't see the snakemake module. This is borken.

cd "`dirname $0`"/..

export RUN_SLOW_TESTS=${RUN_SLOW_TESTS:-0}
export RUN_NETWORK_TESTS=${RUN_NETWORK_TESTS:-1}

# This allows tests to import modules from the test directory, but also we don't
# want any lingering PYTHONPATH in the environment - eg. as set by qc_tools_python.
export PYTHONPATH='./test'

#Test in Py3 only
if [ "$*" == "" ] ; then
    python3 -munittest discover
else
    set -e
    python3 -munittest test.test_"$@"
fi


# Pyflakes is my favoured static analyser for regression testing because it
# just looks at one file at a time, thought it wouldn't hurt to cast
# pylint over the code too.
files_to_flake="*.py"

if [ "$*" == "" ] ; then
    if which pyflakes ; then
        for f in $files_to_flake ; do
            echo "### Running pyflakes $f"
            pyflakes "$f"
        done
    else
        echo "Unable to run pyflakes!"
    fi
fi
