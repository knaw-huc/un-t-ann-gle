#!/usr/bin/env bash
year=$1
#harvestdir=out/230619
harvestdir=out/$(date +"%y%m%d")

poetry run scripts/caf-harvest.py $year
poetry run scripts/ut-untanngle-republic.py -d $harvestdir $year
poetry run scripts/ut-upload-textstores.py -d $harvestdir -t https://textrepo.republic-caf.diginfra.org/api $year
version=$(jq -r ".[\"$year\"]" out/version_id_idx.json)
poetry run scripts/rp-convert-to-web-annotations.py -t https://textrepo.republic-caf.diginfra.org/api/ -v $version -c data/image-to-canvas.csv -o $harvestdir/$year $harvestdir/$year/annotationstore-$year.json
#poetry run scripts/upload-to-annorepo.py -a http://localhost:2023 -c republic-$year -k root $harvestdir/$year/web_annotations.json
poetry run scripts/upload-to-annorepo.py -a https://annorepo.republic-caf.diginfra.org -c $year -l "Republic Year $year" $harvestdir/$year/web_annotations.json