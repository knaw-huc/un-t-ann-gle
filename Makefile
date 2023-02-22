all: help
SHELL=/bin/bash
.PHONY: annotations install help

annotations: out/web_annotations.json

out/web_annotations.json: ./scripts/convert-to-web-annotations.py untanngle/*.py data/image-to-canvas.csv data/1728-annotationstore-220718.json
	poetry run ./scripts/convert-to-web-annotations.py -t https://textrepo.republic-caf.diginfra.org/api/ -v 42df1275-81cd-489c-b28c-345780c3889b -c data/image-to-canvas.csv data/1728-annotationstore-220718.json -o out

install:
	poetry install

help:
	@echo "make-tools for untanngle"
	@echo
	@echo "Please use \`make <target>', where <target> is one of:"
	@echo "  install           		to install the necessary requirements"
	@echo "  annotations          	to generate the web-annotations"
