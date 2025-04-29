#!/usr/bin/env bash
if [[ -z "$REPUBLIC_API_KEY" ]]; then
  echo "set REPUBLIC_API_KEY first!"
  exit 1
fi
date=$(date '+%Y-%m-%d')
./scripts/rp-list-new-annotation-files.sh
poetry run ./scripts/ut-upload-web-annotations.py -a https://annorepo.goetgevonden.nl -c republic-$date -k ${REPUBLIC_API_KEY} $(cat republic-annotation-files.lst)
