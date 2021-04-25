#!/bin/bash

# time: print real in seconds, to simplify parsing
TIMEFORMAT="%3R" # %3U %3S"

if [[ -z "$PASH_TOP" ]]; then
  echo "Need to provide PASH_TOP, possibly $(git rev-parse --show-toplevel)" 1>&2
  exit 1
fi

oneliners_pash(){
  par_times_file="par.res"
  par_outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "oneliners/$par_times_file" ]; then
    echo "skipping oneliners/$par_times_file"
    return 0
  fi
  
  cd oneliners/

  cd ./input/
  ./setup.sh --full
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  if [ "$2" = "--small" ]; then
    scripts_inputs=(
    "nfa-regex;10M.txt"
    "sort;1G.txt"
    "top-n;100M.txt"
    "wf;1G.txt"
    "spell;100M.txt"
    "diff;1G.txt"
    "bi-grams;100M.txt"
    "set-diff;1G.txt"
    "sort-sort;1G.txt"
    "shortest-scripts;all_cmdsx100.txt"
    )
  else
    scripts_inputs=(
      "nfa-regex;100M.txt"
      "sort;3G.txt"
      "top-n;1G.txt"
      "wf;3G.txt"
      "spell;1G.txt"
      "diff;3G.txt"
      "bi-grams;1G.txt"
      "set-diff;3G.txt"
      "sort-sort;1G.txt"
      "shortest-scripts;all_cmdsx100.txt"
    )
  fi

  touch "$par_times_file"
  echo executing one-liners with pash $(date) | tee -a "$par_times_file"
  echo '' >> "$par_times_file"

  for script_input in ${scripts_inputs[@]}
  do
    IFS=";" read -r -a script_input_parsed <<< "${script_input}"
    script="${script_input_parsed[0]}"
    input="${script_input_parsed[1]}"
    export IN="$PASH_TOP/evaluation/benchmarks/oneliners/input/$input"
    printf -v pad %30s
    padded_script="${script}.sh:${pad}"
    padded_script=${padded_script:0:30}

    par_outputs_file="${outputs_dir}/${script}.${par_outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$par_outputs_file"; } 2>&1) | tee -a "$par_times_file"
  done

  cd ..
}

unix50_pash(){
  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "unix50/${times_file}" ]; then
    echo "skipping unix50/${times_file}"
    return 0
  fi

  cd unix50/

  cd input/
  if [ "$2" = "--full" ]; then
    export IN_PRE=$PASH_TOP/evaluation/benchmarks/unix50/input/
    ./setup.sh --full
  else
    ./setup.sh --small
    export IN_PRE=$PASH_TOP/evaluation/benchmarks/unix50/input/small
  fi


  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  touch "$times_file"
  echo executing Unix50 $(date) | tee -a "$times_file"
  echo '' >> "$times_file"

  # FIXME this is the input prefix; do we want all to be IN 
  #export IN_PRE=$PASH_TOP/evaluation/benchmarks/unix50/input

  for number in `seq 36`
  do
    script="${number}"
    
    printf -v pad %20s
    padded_script="${script}.sh:${pad}"
    padded_script=${padded_script:0:20}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --speculation quick_abort --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done  
  cd ..
}

web-index_pash(){
  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "web-index/${times_file}" ]; then
    echo "skipping web-index/${times_file}"
    return 0
  fi

  cd web-index/

  cd input/
  ./setup.sh
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"
  
  touch "$times_file"
  echo executing web index with pash $(date) | tee -a "$times_file"
  export IN=$PASH_TOP/evaluation/benchmarks/web-index/input/1000.txt
  export WEB_INDEX_DIR=$PASH_TOP/evaluation/benchmarks/web-index/input
  export WIKI=$PASH_TOP/evaluation/benchmarks/web-index/input/
  outputs_file="${outputs_dir}/web-index.${outputs_suffix}"
  pash_log="${pash_logs_dir}/web-index.pash.log"

  ## FIXME: There is a bug when running with r_split at the moment. r_wrap cannot execute bash_functions
  echo web-index.sh: $({ time "$PASH_TOP/pa.sh" --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" web-index.sh > "${outputs_file}"; } 2>&1) | tee -a "$times_file"
  cd ..
}

max-temp_pash(){
  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "max-temp/${times_file}" ]; then
    echo "skipping max-temp/${times_file}"
    return 0
  fi

  cd max-temp/

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  touch "$times_file"
  echo executing max temp with pash $(date) | tee -a "$times_file"
  outputs_file="${outputs_dir}/max-temp.${outputs_suffix}"
  pash_log="${pash_logs_dir}/max-temp.pash.log"
  echo mex-temp.sh: $({ time time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" max-temp.sh > "${outputs_file}"; } 2>&1) | tee -a "$times_file"
  cd ..
}

analytics-mts_pash(){
  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "analytics-mts/${times_file}" ]; then
    echo "skipping analytics-mts/${times_file}"
    return 0
  fi

  cd analytics-mts/

  cd input/

  if [ "$2" = "--full" ]; then
    export IN="input/in.full.csv"
    ./setup.sh --full
  else
    ./setup.sh --small
    export IN="input/in.small.csv"
  fi
  cd ..



  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  touch "$times_file"
  echo executing MTS analytics with pash $(date) | tee -a "$times_file"
  ## FIXME 5.sh is not working yet
  for number in `seq 4`
  do
    script="${number}"
    
    printf -v pad %20s
    padded_script="${script}.sh:${pad}"
    padded_script=${padded_script:0:20}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done
  cd ..
}

poets_pash(){
  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "poets/${times_file}" ]; then
    echo "skipping poets/${times_file}"
    return 0
  fi

  cd poets/

  cd input/
  if [ "$2" = "--full" ]; then
    export IN="input/pg/"
    ./setup.sh --full
  else
    ./setup.sh --small
    export IN="input/small/"
  fi
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  names_scripts=(
    "1syllable_words;6_4"
    "2syllable_words;6_5"
    "4letter_words;6_2"
    "bigrams_appear_twice;8.2_2"
    "bigrams;4_3"
    "compare_exodus_genesis;8.3_3"
    "count_consonant_seq;7_2"
    # "count_morphs;7_1"
    "count_trigrams;4_3b"
    "count_vowel_seq;2_2"
    "count_words;1_1"
    "find_anagrams;8.3_2"
    "merge_upper;2_1"
    "sort;3_1"
    "sort_words_by_folding;3_2"
    "sort_words_by_num_of_syllables;8_1"
    "sort_words_by_rhyming;3_3"
    # "trigram_rec;6_1"
    "uppercase_by_token;6_1_1"
    "uppercase_by_type;6_1_2"
    "verses_2om_3om_2instances;6_7"
    "vowel_sequencies_gr_1K;8.2_1"
    "words_no_vowels;6_3"
  )

  touch "$times_file"
  echo executing Unix-for-poets with pash $(date) | tee -a "$times_file"
  echo '' >> "$times_file"

  for name_script in ${names_scripts[@]}
  do
    IFS=";" read -r -a name_script_parsed <<< "${name_script}"
    name="${name_script_parsed[0]}"
    script="${name_script_parsed[1]}"
    printf -v pad %30s
    padded_script="${name}.sh:${pad}"
    padded_script=${padded_script:0:30}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done
  cd ..
}



# everything under this line is WIP


dgsh_pash(){

  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "dgsh/${times_file}" ]; then
    echo "skipping dgsh/${times_file}"
    return 0
  fi

  cd dgsh/

  cd input/
  ./setup.sh
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  names_scripts=(
    "compressionbench;1"
    "gitstats;2"
    "cmetrics;3"
    "dublicatefiles;4"
    "highlightwords;5"
    # "wordproperties;6"
    # "weatherreport;7"
    "textproperties;8"
    "staticsymbols;9"
    # "hierarchymap;10"
    # "plotgit;11"
    "parallelword;12"
    # "venuauthor;13"
    # "2dfourier;14"
    # "nuclear;15"
    # "fft;16"
    "reordercol;17"
    "dirlisting;18"
  )

  touch "$times_file"
  echo executing DGSH with pash $(date) | tee -a "$times_file"
  echo '' >> "$times_file"

  export VOC=/usr/share/dict/words
  export IN=$PASH_TOP/evaluation/benchmarks/dgsh/input/
  export FULL=$IN/dblp.xml
  export MINI=$IN/mini.xml
  export OUT=$PASH_TOP/evaluation/benchmarks/dgsh/input/
  export BIN=/usr/local/bin

  for name_script in ${names_scripts[@]}
  do
    IFS=";" read -r -a name_script_parsed <<< "${name_script}"
    name="${name_script_parsed[0]}"
    script="${name_script_parsed[1]}"
    export IN="$PASH_TOP/evaluation/benchmarks/dgsh/input/genesis"
    printf -v pad %30s
    padded_script="${name}.sh:${pad}"
    padded_script=${padded_script:0:30}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done
  cd ..
}


aliases_pash(){

  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "aliases/${times_file}" ]; then
    echo "skipping aliases/${times_file}"
    return 0
  fi

  cd aliases/

  cd input/
  ./setup.sh
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  names_scripts=(
    "compressionbench;1"
    "gitstats;2"
    "cmetrics;3"
    "dublicatefiles;4"
    "highlightwords;5"
    # "wordproperties;6"
    # "weatherreport;7"
    "textproperties;8"
    "staticsymbols;9"
    # "hierarchymap;10"
    # "plotgit;11"
    "parallelword;12"
    # "venuauthor;13"
    # "2dfourier;14"
    # "nuclear;15"
    # "fft;16"
    "reordercol;17"
    "dirlisting;18"
  )

  touch "$times_file"
  echo executing aliases with pash $(date) | tee -a "$times_file"
  echo '' >> "$times_file"


  for name_script in ${names_scripts[@]}
  do
    IFS=";" read -r -a name_script_parsed <<< "${name_script}"
    name="${name_script_parsed[0]}"
    script="${name_script_parsed[1]}"
    export IN="$PASH_TOP/evaluation/benchmarks/aliases/input/genesis"
    printf -v pad %30s
    padded_script="${name}.sh:${pad}"
    padded_script=${padded_script:0:30}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done
  cd ..
}



posh_pash(){

  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "posh/${times_file}" ]; then
    echo "skipping posh/${times_file}"
    return 0
  fi

  cd posh/

  cd input/
  ./setup.sh
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  names_scripts=(
    "discat;1"
    "convert;2"
    "raytracing;3"
    # "zannotate;4" where is zannotate binary
  )

  touch "$times_file"
  echo executing posh with pash $(date) | tee -a "$times_file"
  echo '' >> "$times_file"

  export OUT=$PASH_TOP/evaluation/benchmarks/posh/input/output
  for name_script in ${names_scripts[@]}
  do
    IFS=";" read -r -a name_script_parsed <<< "${name_script}"
    name="${name_script_parsed[0]}"
    script="${name_script_parsed[1]}"
    printf -v pad %30s
    padded_script="${name}.sh:${pad}"
    padded_script=${padded_script:0:30}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done
  cd ..
}

bio_pash(){

  times_file="par.res"
  outputs_suffix="par.out"
  outputs_dir="outputs"
  pash_logs_dir="pash_logs"
  width=16
  if [ -e "bio/${times_file}" ]; then
    echo "skipping bio/${times_file}"
    return 0
  fi

  cd bio/

  cd input/
  ./setup.sh
  cd ..

  mkdir -p "$outputs_dir"
  mkdir -p "$pash_logs_dir"

  names_scripts=(
    "bio4.sh;bio4"
  )

  touch "$times_file"
  echo executing bio with pash $(date) | tee -a "$times_file"
  echo '' >> "$times_file"

  export OUT=$PASH_TOP/evaluation/benchmarks/bio/input/output
  for name_script in ${names_scripts[@]}
  do
    IFS=";" read -r -a name_script_parsed <<< "${name_script}"
    name="${name_script_parsed[0]}"
    script="${name_script_parsed[1]}"
    printf -v pad %30s
    padded_script="${name}.sh:${pad}"
    padded_script=${padded_script:0:30}

    outputs_file="${outputs_dir}/${script}.${outputs_suffix}"
    pash_log="${pash_logs_dir}/${script}.pash.log"

    echo "${padded_script}" $({ time "$PASH_TOP/pa.sh" --r_split --dgsh_tee -d 1 -w "${width}" --log_file "${pash_log}" ${script}.sh > "$outputs_file"; } 2>&1) | tee -a "$times_file"
  done
  cd ..
}

#time $1 $@
