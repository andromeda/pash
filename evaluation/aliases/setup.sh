# remove this line since it hangs timeout 2 -i brightness | cut -f2 -d "" "" > ~/.currentbrightness; cat\
# execute once
#sed -e '46106d' $1                                                               
# likely-longest-pipelines.txt is locally stored
# strip the number of pipe column
cut -f1 -d" " --complement  likely-longest-pipelines.txt > $PASH_TOP/evaluation/scripts/input/generated.file
