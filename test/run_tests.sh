#!/bin/bash

# When running the tests, we need to ensure Python picks up the right environment.
# For this reason it's worth having a test wrapper.

cd "`dirname $0`"/..

# Most tests currently pass using the system Python3 but really you should test with
# the VEnv Python3. Let's activate this for you now, before we 'set -eu'.
if [ -n "$VIRTUAL_ENV" ] ; then
    echo "Virtual Env already active: $VIRTUAL_ENV"
elif [ -e _illuminatus_venv ] ; then
    echo "Running: source ./_illuminatus_venv/bin/activate"
    source ./_illuminatus_venv/bin/activate
    if [ "$(readlink -f "$(dirname "$(which python3)")")/python3" != \
         "$(readlink -f _illuminatus_venv)/bin/python3" ] ; then
        echo "FAILED - python3 is $(which python3) not $(readlink -f _illuminatus_venv)/bin/python3"
        exit 1
    fi
else
    echo "No ./_illuminatus_venv; will proceeed using the default $(which python3)"
fi

# This needs to come after the VEnv activation
set -euo pipefail

# This allows tests to import modules from the test directory, but also we don't
# want any lingering PYTHONPATH in the environment - eg. as set by qc_tools_python.
# Same for BASH_ENV
export PYTHONPATH='./test'
unset BASH_ENV

# Test in Py3 only. Get coverage as we go, if we can.
if [ which coverage >&/dev/null ] ; then
    ut=(coverage run --source=. --omit=test/* -m unittest)
    coverage=(coverage)
else
    ut=(python3 -m unittest)
    coverage=(true) # ie. pass
fi
if [ "$*" == "" ] ; then
    "${ut[@]}" discover
    "${coverage[@]}" report
else
    set -e
    "${ut[@]}" test.test_"$@"
fi


# Pyflakes is my favoured static analyser for regression testing because it
# just looks at one file at a time, thought it wouldn't hurt to cast
# pylint over the code too.
# Don't quit on error here.
files_to_flake="*.py"

echo
if [ "$*" == "" ] ; then
    if which pyflakes ; then
        for f in $files_to_flake ; do
            echo "### Running pyflakes $f"
            pyflakes "$f" || true
        done
    else
        echo "Unable to run pyflakes!"
    fi
fi
