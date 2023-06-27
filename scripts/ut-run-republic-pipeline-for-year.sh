#!/usr/bin/env bash

set -e
[[ -t 1 ]] || export TERM=dumb
txtylw=$(tput setaf 11)
txtwht=$(tput setaf 7)
year=$1
envfile=$2
startstage=$3
if [[ -z "$startstage" ]]; then
  startstage=1
fi

check_env_var_is_set(){
  name=$1
  var=$2
  if [[ -z "$var" ]]; then
    echo "error: variable $name not set!"
    some_variables_not_set=true
  fi
}

#harvestdir=out/230619
harvestdir=out/$(date +"%y%m%d")

check_env_var_is_set "envfile" $envfile
check_env_var_is_set "year" $year
if [ ${some_variables_not_set} ]; then
  exit 1
fi

source $envfile
check_env_var_is_set "ANNO_URL" $ANNO_URL
check_env_var_is_set "PROV_URL" $PROV_URL
check_env_var_is_set "PROV_KEY" $PROV_KEY
if [ ${some_variables_not_set} ]; then
  exit 1
fi

echo "starting pipeline for $year"

if [[ $startstage -le 1 ]]; then
  echo "${txtylw}[1/6] harvesting data from CAF${txtwht}"
  poetry run scripts/caf-harvest.py $year
  echo
fi

if [[ $startstage -le 2 ]]; then
  echo "${txtylw}[2/6] untanngling caf harvest${txtwht}"
  poetry run scripts/ut-untanngle-republic.py -d $harvestdir $year
  echo
fi

if [[ $startstage -le 3 ]]; then
  echo "${txtylw}[3/6] uploading extracted textstore${txtwht}"
  poetry run scripts/ut-upload-textstores.py \
    -d $harvestdir \
    -t https://textrepo.republic-caf.diginfra.org/api \
    --provenance-base-url $PROV_URL \
    --provenance-api-key $PROV_KEY \
    $year
  echo
fi

if [[ $startstage -le 4 ]]; then
  version=$(jq -r ".[\"$year\"]" out/version_id_idx.json)
  echo "${txtylw}[4/5] converting annotationstore to web annotations${txtwht}"
  poetry run scripts/rp-convert-to-web-annotations.py \
    -t https://textrepo.republic-caf.diginfra.org/api/ \
    -v $version \
    -c data/image-to-canvas.csv \
    -o $harvestdir/$year \
    $harvestdir/$year/annotationstore-$year.json
  echo
fi

if [[ $startstage -le 5 ]]; then
  echo "${txtylw}[5/6] uploading web annotations to annorepo server${txtwht}"
  poetry run scripts/ut-upload-web-annotations.py -a $ANNO_URL -c republic -k root $harvestdir/$year/web_annotations.json
  echo
fi

if [[ $startstage -le 6 ]]; then
  echo "${txtylw}[6/6] uploading provenance for web annotations${txtwht}"
  poetry run scripts/rp-upload-annotation-provenance.py $year
  echo
fi
