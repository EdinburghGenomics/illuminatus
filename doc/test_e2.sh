#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

echo "Some obscure BASH behaviour here"
echo "On CentOS 7 this prints '1' and 'Caught The Exception' for 2 and 3 and 4"
echo "On CentOS 8 this only works for version 4"

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
{ eval foo ; true ; } || echo Caught The Exception 3
set -e
{ eval foo ; } ; [ $? = 0 ] || echo Caught The Exception 4
