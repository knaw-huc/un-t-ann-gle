all: help
SHELL=/bin/bash

data/republic-volumes.csv: data/pim-republic-imagesets.json scripts/rp-extract-volume-data.py
	poetry run scripts/rp-extract-volume-data.py

data/image-to-canvas.csv: data/republic-volumes.csv scripts/rp-extract-image-to-canvas.sh
	./scripts/rp-extract-image-to-canvas.sh

out/web_annotations.json: ./scripts/convert-to-web-annotations.py untanngle/*.py data/image-to-canvas.csv data/1728-annotationstore-220718.json
	poetry run ./scripts/convert-to-web-annotations.py -t https://textrepo.republic-caf.diginfra.org/api/ -v 42df1275-81cd-489c-b28c-345780c3889b -c data/image-to-canvas.csv data/1728-annotationstore-220718.json -o out

.PHONY: republic-annotations
republic-annotations: out/web_annotations.json

out/mondriaan-web-annotations.json: ./scripts/ut-convert-mondriaan.py untanngle/*.py data/mondriaan-anno.json data/mondriaan-text.json
	poetry run scripts/ut-convert-mondriaan.py > out/mondriaan-web-annotations.json

.PHONY: mondriaan-annotations
mondriaan-annotations: out/mondriaan-web-annotations.json

.PHONY: install
install:
	poetry install
.PHONY: republic-1706
republic-1706:
	./scripts/ut-run-republic-pipeline-for-year.sh 1706 conf/republic-local.env

.PHONY: help
help:
	@echo "make-tools for untanngle"
	@echo
	@echo "Please use \`make <target>', where <target> is one of:"
	@echo "  install                - to install the necessary requirements"
	@echo
	@echo "  republic-annotations   - to generate the republic web-annotations"
	@echo "  republic-1706          - to run the republic untangle pipeline for 1706"
	@echo
	@echo "  mondriaan-annotations  - to generate the mondriaan web-annotations"

