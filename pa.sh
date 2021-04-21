#!/usr/bin/env bash

export PASH_TOP=${PASH_TOP:-${BASH_SOURCE%/*}}
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib/"

if [ "$#" -eq 1 ] && [ "$1" = "--init" ]; then
  $PASH_TOP/compiler/superoptimize.sh
  exit
fi

if ! command -v python3 &> /dev/null
then
    echo "Python >=3 could not be found"
    exit
fi

PASH_FROM_SH="pa.sh" python3 -S $PASH_TOP/compiler/pash.py "$@"
