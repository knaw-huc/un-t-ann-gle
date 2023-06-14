#!/usr/bin/env bash

lines=$(grep http data/republic-volumes.csv | sed -e "s/.*http/http/g")

for line in $lines; do
  uri=${line//[$'\t\r\n']} # remove line endings
  echo "<= ${uri}"
  curl --silent $uri | jq  -r '.sequences[].canvases[] | [.label,."@id"] | @csv' >> data/image-to-canvas.csv.tmp
done
sort -u < data/image-to-canvas.csv.tmp > data/image-to-canvas.csv