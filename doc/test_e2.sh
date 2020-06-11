#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

echo "Some obscure BASH behaviour here"
echo "On CentOS 7 this prints '1' and 'Caught The Exception'"

foo(){

   set +e ; ( set -e ;

    false ## An error!
    echo "This should not print"

   ) |& cat ; retval=$?
   echo $retval
   return $retval
}

{ true && eval foo && true ; } || echo Caught The Exception
