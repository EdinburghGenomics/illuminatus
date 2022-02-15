#!/bin/bash

# Default jobscript for Snakemake on the GSEG environment.
# Made by Tim B on 2016-11-01
# Updated after DRMAA fix on 2017-06-13

# Where am I running? Weird syntax avoids fopen on /dev/stderr
# which is bad if /dev/stderr is a real file.
# Could add more debugging info here, maybe?
echo "Running on `hostname`" | tee >(cat >&2)

# Set TMPDIR, which most programs will respect, including Picard if run
# via my wrapper scripts.
export TMPDIR=/lustre-gseg/tmp/"$USER@$HOSTNAME"
mkdir -p "$TMPDIR"

# Also, we can have a pre-run script.  Useful for qc_tools_python/activate
# and any other case where you want specific settings on each node.
# Under Snakemake+SLURM, you can simply set this as an env var.
if [ -r "$SNAKE_PRERUN" ] ; then
    echo "+ source $SNAKE_PRERUN" >&2
    source "$SNAKE_PRERUN"
fi

# properties = {properties}
{exec_job}
