#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

echo "Some obscure BASH behaviour here"
echo "On CentOS 7 this prints '1' and 'Caught The Exception' for 2 and 3"

foo(){

   set +e ; ( set -e ;

    false ## An error!
    echo "This should not print"

   ) |& cat ; retval=$?
   echo $retval
   return $retval
}

set -e
foo || echo Caught The Exception 1
set -e
eval foo || echo Caught The Exception 2
set -e
{ eval foo ; } || echo Caught The Exception 3
