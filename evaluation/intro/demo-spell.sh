#!/bin/sh

cd "$(dirname $0)"

[ -z $PASH_TOP ] && { 
  echo "PASH_TOP not set, maybe $(git rev-parse --show-toplevel)?"
  exit
}
FILE="input/100M.txt"
DICT="input/sorted_words"

cat "$FILE" | tr A-Z a-z | tr -cs A-Za-z '\n' | sort | uniq | comm -13 $DICT -
