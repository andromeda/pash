#!/bin/bash

# Package several versions of PaSh:
# * a shallow-clone version for a quick-install from `up`
# * a deep-clone version for other environments TODO
# * a docker image running on ubuntu 18.04 TODO

set -ex

echo $(pwd)
REV=0

REV=$(git rev-parse --short HEAD)
cd ../../

# # Shallow clone --- might not be ideal for development
# git clone --depth 1 git@github.com:andromeda/pash.git
# mv pash pash-shallow
# tar -cvzf pash-shallow.tar.gz pash-shallow/ > /dev/null
# # uncomment the following line to keep all versions
# # mv pash.tar.gz get/pash-${REV}.tar.gz
# # ln -sf ./pash-${REV}.tar.gz get/latest 
# mv pash-shallow.tar.gz get/
# ln -sf ./pash-shallow.tar.gz get/latest 
# rm -rf pash-shallow

cd pash
git pull
cd ..
tar -cvzf pash.tar.gz ./pash > /dev/null
mkdir -p get
mv pash.tar.gz get/
ln -sf ./pash.tar.gz get/latest 

# in the future, we might want to have versions
# ln -s pash.tar.gz latest


# TODO: for a clear release, remove all versioning artifacts
# cp -r pash release
# cd release
# rm -rf .gitignore .gitsubmodules .git
# cd ..

