#!/bin/bash

set -e

PASH_TOP=${PASH_TOP:-$(git rev-parse --show-toplevel)}

## FIXME: These inputs are already 1G when downloaded
## FIXME: Also, wget is not silent like curl in the other setup scripts.

inputs=(
  1 10 11 12 2 3 4 5 6 7 8 9.1 9.2 9.3 9.4 9.5 9.6 9.7 9.8 9.9
)

if [[ "$1" == "-c" ]]; then
  for input in ${inputs[@]}
  do
    rm -f "${input}.txt"
    rm -rf small
  done
  exit
fi

for input in ${inputs[@]}
do
  if [ ! -f "${input}.txt" ]; then
    wget "http://ndr.md/data/unix50/${input}.txt"
    "$PASH_TOP/scripts/append_nl_if_not.sh" "${input}.txt"
  fi
done

## FIXME: Calling this script with --full is not idempotent.
if [ "$#" -eq 1 ] && [ "$1" = "--full" ]; then
  for file in *.txt; do
    echo '' > temp.txt
    for (( i = 0; i < 10; i++ )); do
      cat $file >> temp.txt
    done
    mv temp.txt $file
  done
fi



## FIXME: Calling this script with --full is not idempotent.
if [ "$#" -eq 1 ] && [ "$1" = "--small" ]; then
  if [ ! -e ./small ]; then
    mkdir small
    for file in *.txt; do
      cat $file | head -n 5000000 > small/$file
    done
  fi
fi






if [ "$#" -eq 1 ] && [ "$1" = "--gen-full" ]; then
  echo Generting full-size inputs

  for file in *.txt; do
    new_file=$(basename $file .txt).1G.txt
    max=$(echo "1000000000 / $(stat --printf="%s\n" $file)" | bc)
    echo "generating 1-G $new_file (${max}x increase)"
    for (( i = 0; i < max ; i++ )); do
      cat $file >> $new_file;
    done
  done
fi
