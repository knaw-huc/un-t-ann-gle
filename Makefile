all: help
SHELL=/bin/bash

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

.PHONY: help
help:
	@echo "make-tools for untanngle"
	@echo
	@echo "Please use \`make <target>', where <target> is one of:"
	@echo "  install           		to install the necessary requirements"
	@echo "  republic-annotations	to generate the republic web-annotations"
	@echo "  mondriaan-annotations	to generate the mondriaan web-annotations"
