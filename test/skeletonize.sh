#!/bin/bash
set -euo pipefail

# Something I seem to do quite a lot in making tests.
# Take a source folder and make a copy of it but all the files are zero size.
# Also supports making a symlink farm.

# usage: skeletonize.sh <zero|link> /exisisting/dir [/target/dir]

mode="$1"
from="$2"
to="${3:-.}"

# Mode must be zero or link
if ! [ "$mode" = zero -o "$mode" = link ] ; then
    echo "Mode must be zero or link"
    exit 1
fi

if ! [ -d "$from" ] ; then
    echo "No such directory: $from"
    exit 1
fi

if ! [ -d "$to" ] ; then
    echo "No such directory: $to"
    exit 1
fi

from="`readlink -f $from`"
to="`readlink -f $to`/`basename $from`"

if [ -e "$to" ] ; then
    echo "Path already exists: $to"
    exit 1
fi

# Right, on we go. Make all the non-empty folders.
mkdir -vp "$to"
( cd "$from" &&
  find -type f -print0 | sed -z 's,/[^/]*$,,' | uniq -z | ( cd "$to" && xargs -0 -i mkdir -vp "{}" )
)

# Now make the links, or a bunch of empty files.
if [ "$mode" = zero ] ; then (
  cd "$from" &&
  find -type f -print0 | xargs -0 -i echo "touch {}"
  find -type f -print0 | ( cd "$to" && xargs -0 -i touch "{}" )
) ; fi

if [ "$mode" = link ] ; then (
  cd "$from" &&
  find -type f -print0 | ( cd "$to" && xargs -0 -i ln -vs "$from/{}" "{}" )
) ; fi

echo
echo "DONE - here's the tree..."
tree -hlF "$to"
