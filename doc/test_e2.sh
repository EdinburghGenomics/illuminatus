#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

echo "Some obscure BASH behaviour here"
echo "On CentOS 7 this prints '1' and 'Caught The Exception' for 2 and 3"

foo(){

   ( set -e ; 

    false ## An error!
    echo "This should not print"

   ) |& cat ; retval=$?
   echo $retval
   return $retval
}

foo || echo Caught The Exception 1
eval foo || echo Caught The Exception 2
{ eval foo ; } || echo Caught The Exception 3
