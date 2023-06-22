#!/usr/bin/env bash
year=$1
envfile=$2

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

echo "[1/5] harvesting data from CAF"
poetry run scripts/caf-harvest.py $year

echo "[2/5] untanngling caf harvest"
poetry run scripts/ut-untanngle-republic.py -d $harvestdir $year

echo "[3/5] uploading extracted textstore"
poetry run scripts/ut-upload-textstores.py -d $harvestdir -t https://textrepo.republic-caf.diginfra.org/api --provenance-base-url $PROV_URL -provenance-api-key $PROV_KEY $year

version=$(jq -r ".[\"$year\"]" out/version_id_idx.json)
echo "[4/5] converting annotationstore to web annotations"
poetry run scripts/rp-convert-to-web-annotations.py -t https://textrepo.republic-caf.diginfra.org/api/ -v $version -c data/image-to-canvas.csv -o $harvestdir/$year $harvestdir/$year/annotationstore-$year.json

echo "[5/5] uploading web annotations to annorepo server"
poetry run scripts/upload-to-annorepo.py -a $ANNO_URL -c republic -k root $harvestdir/$year/web_annotations.json
