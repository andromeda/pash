#!/bin/bash

# #Check that we are in the appropriate directory where setup.sh is
# #https://stackoverflow.com/a/246128
# DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# echo "changing to $DIR to run setup.sh"
# cd $DIR

PASH_TOP=${PASH_TOP:-$(git rev-parse --show-toplevel)}

if [[ "$1" == "-c" ]]; then
    rm -f *.bz2 'in.csv'
    rm -f 'in.full.csv'
    rm -f 'in.small.csv'
    exit
fi

if [ ! -f ./in.csv ]; then
  # yesterday=$(date --date='1 days ago' +'%y-%m-%d')
  # curl https://www.balab.aueb.gr/~dds/oasa-$yesterday.bz2 |
  curl -sf 'https://www.balab.aueb.gr/~dds/oasa-2021-01-08.bz2' | bzip2 -d > in.csv
  if [ $? -ne 0 ]; then
    echo "oasa-2021-01-08.bz2 / bzip2 not available, contact the pash authors"
    exit 1
  fi
  "$PASH_TOP/scripts/append_nl_if_not.sh"  in.csv
fi


if [ "$#" -eq 1 ] && [ "$1" = "--small" ];   then
  if [ ! -f ./in.small.csv ]; then
    file=in.small.csv
    cat in.csv > $file
    cat in.csv >> $file
  fi 
elif  [ "$#" -eq 1 ] && [ "$1" = "--full" ]; then
  if [ ! -f ./in.full.csv ]; then
    file=in.full.csv
    for (( i = 0; i < 4 ; i++ )); do
      cat in.csv >> $file;
    done
  fi
fi
