#!/usr/bin/env bash

lines=$(grep http data/republic-volumes.csv | sed -e "s/.*http/http/g")
tmpfile=data/image-to-canvas.csv.tmp

for line in $lines; do
  uri=${line//[$'\t\r\n']} # remove line endings
  echo "<= ${uri}"
  curl --silent $uri | jq  -r '.sequences[].canvases[] | [.label,."@id"] | @csv' >> $tmpfile
done
sort -u < $tmpfile > data/image-to-canvas.csv && rm $tmpfile