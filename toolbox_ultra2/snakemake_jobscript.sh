#!/bin/bash

# Default jobscript for Snakemake on the ULTRA2 environment.
# Maybe not used if we're not firing jobs via SLURM?

# Set TMPDIR, which most programs will respect, including Picard if run
# via my wrapper scripts.
export TMPDIR=/tmp/"$USER@$HOSTNAME"
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
