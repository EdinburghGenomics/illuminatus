#!/bin/bash

# When running the tests, we need to ensure Python picks up the right environment.
# For this reason ,it's worth having a test wrapper.
cd "`dirname $0`"/..

export RUN_SLOW_TESTS=${RUN_SLOW_TESTS:-0}
export RUN_NETWORK_TESTS=${RUN_NETWORK_TESTS:-1}

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
PYFLAKES="/ifs/software/linux_x86_64/python/python_2.7.10_venv/bin/pyflakes"
files_to_flake="*.py"

if [ "$*" == "" ] ; then
    if [ -x "$PYFLAKES" ] ; then
        for f in $files_to_flake ; do
            echo "### Running pyflakes $f"
            "$PYFLAKES" "$f"
        done
    else
        echo "Unable to run $PYFLAKES!"
    fi
fi
