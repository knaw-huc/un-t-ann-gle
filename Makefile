all: help
SHELL=/bin/bash
include .local/.env

.PHONY: install
install:
	poetry install

# republic
data/republic-volumes.csv: data/pim-republic-imagesets.json scripts/rp-extract-volume-data.py
	poetry run scripts/rp-extract-volume-data.py

data/image-to-canvas.csv: data/republic-volumes.csv scripts/rp-extract-image-to-canvas.sh
	./scripts/rp-extract-image-to-canvas.sh

out/web_annotations.json: ./scripts/convert-to-web-annotations.py untanngle/*.py data/image-to-canvas.csv data/1728-annotationstore-220718.json
	poetry run ./scripts/convert-to-web-annotations.py -t https://textrepo.republic-caf.diginfra.org/api/ -v 42df1275-81cd-489c-b28c-345780c3889b -c data/image-to-canvas.csv data/1728-annotationstore-220718.json -o out

.PHONY: republic-annotations
republic-annotations:
	for y in {1705..1796}; do ./scripts/ut-run-republic-pipeline-for-year.sh $$y conf/republic-local.env; done

.PHONY: republic-1706
republic-1706:
	./scripts/ut-run-republic-pipeline-for-year.sh 1706 conf/republic-local.env

.PHONY: republic-1796
republic-1796:
	./scripts/ut-run-republic-pipeline-for-year.sh 1796 conf/republic-local.env

#translatin
.PHONY: translatin-untangle
translatin-untangle:
	(cd data/translatin && rsync -cav tt-docker-vm:/data/deploy/translatin/watm/$(TRANSLATIN_VERSION) .)
	poetry run ./scripts/ut-convert-translatin.py $(TRANSLATIN_VERSION)

.PHONY: translatin-upload-annotations
translatin-upload-annotations: scripts/ut-upload-web-annotations.py out/translatin/web-annotations.json
	poetry run scripts/ut-upload-web-annotations.py -a https://annorepo.translatin.huygens.knaw.nl -c translatin-$(TRANSLATIN_VERSION) --overwrite-existing-container -l "Translatin (watm $(TRANSLATIN_VERSION))" -k $(TRANSLATIN_API_KEY) out/translatin/web-annotations.json

# mondriaan
.PHONY: mondriaan-untangle
mondriaan-untangle:
	(cd data/mondriaan && git pull)
	poetry run ./scripts/ut-convert-mondriaan.py $(MONDRIAAN_VERSION)

.PHONY: mondriaan-upload-annotations
mondriaan-upload-annotations: scripts/ut-upload-web-annotations.py out/mondriaan/web-annotations.json
	poetry run scripts/ut-upload-web-annotations.py -a https://mondriaan.annorepo.dev.clariah.nl -c mondriaan-$(MONDRIAAN_VERSION) -l "Correspondence of Mondriaan (watm $(MONDRIAAN_VERSION))" -k $(MONDRIAAN_API_KEY) out/mondriaan/web-annotations.json

# suriano
.PHONY: suriano-untangle
suriano-untangle:
	(cd data/suriano && rsync -cav tt-docker-vm:/data/deploy/suriano/watm/$(SURIANO_VERSION) .)
	poetry run ./scripts/ut-convert-suriano.py $(SURIANO_VERSION)

.PHONY: suriano-upload-annotations
suriano-upload-annotations: scripts/ut-upload-web-annotations.py out/suriano/web-annotations.json
#	poetry run scripts/ut-upload-web-annotations.py -a http://localhost:8080 -c suriano-$(SURIANO_VERSION) -l "Correspondence of Christofforo Suriano (watm $(SURIANO_VERSION))" -k $(SURIANO_API_KEY) out/suriano/web-annotations.json
	poetry run scripts/ut-upload-web-annotations.py -a https://annorepo.suriano.huygens.knaw.nl -c suriano-$(SURIANO_VERSION) -l "Correspondence of Christofforo Suriano (watm $(SURIANO_VERSION))" -k $(SURIANO_API_KEY) out/suriano/web-annotations.json
#	poetry run scripts/ut-upload-web-annotations.py -a https://suriano.annorepo.dev.clariah.nl -c suriano-$(SURIANO_VERSION) -l "Correspondence of Christofforo Suriano (watm $(SURIANO_VERSION))" -k $(SURIANO_API_KEY) out/suriano/web-annotations.json

# vangogh
.PHONY: vangogh-untangle
vangogh-untangle:
	(cd data/vangogh && git pull)
	poetry run ./scripts/ut-convert-vangogh.py $(VANGOGH_VERSION)

.PHONY: vangogh-upload-annotations
vangogh-upload-annotations: scripts/ut-upload-web-annotations.py out/vangogh/web-annotations.json
	poetry run scripts/ut-upload-web-annotations.py -a https://vangogh.annorepo.dev.clariah.nl -c vangogh-$(VANGOGH_VERSION) -l "Correspondence of Vincent van Gogh (watm $(VANGOGH_VERSION))" -k $(VANGOGH_API_KEY) out/vangogh/web-annotations.json

.PHONY: editem-docker-image
editem-docker-image:
	docker build --tag $(EDITEM_TAG) -f docker/editem/Dockerfile .
	docker push $(EDITEM_TAG)

.PHONY: help
help:
	@echo "make-tools for untanngle"
	@echo
	@echo "Please use \`make <target>', where <target> is one of:"
	@echo "  install                      - to install the necessary requirements"
	@echo
	@echo "  suriano-untangle             - to untangle the textfabric export for suriano ($(SURIANO_VERSION))"
	@echo "  suriano-upload-annotations   - to upload the web annotations for suriano ($(SURIANO_VERSION))"
	@echo
	@echo "  translatin-untangle           - to untangle the textfabric export for translatin ($(TRANSLATIN_VERSION))"
	@echo "  translatin-upload-annotations - to upload the web annotations for translatin ($(TRANSLATIN_VERSION))"
	@echo
	@echo "  mondriaan-untangle           - to untangle the textfabric export for mondriaan ($(MONDRIAAN_VERSION))"
	@echo "  mondriaan-upload-annotations - to upload the web annotations for mondriaan ($(MONDRIAAN_VERSION))"
	@echo
	@echo "  vangogh-untangle             - to untangle the textfabric export for vangogh ($(VANGOGH_VERSION))"
	@echo "  vangogh-upload-annotations   - to upload the web annotations for vangogh ($(VANGOGH_VERSION))"
	@echo
	@echo "  israels-untangle             - to untangle the textfabric export for israels ($(ISRAELS_VERSION))"
	@echo "  israels-upload-annotations   - to upload the web annotations for israels ($(ISRAELS_VERSION))"
	@echo
#	@echo "  editem-docker-image          - to build a docker image for the conversion of editem TextFabric WATM output"
#	@echo "                                 to records in TextRepo and AnnoRepo and push it to registry.diginfra.net"
	@echo "NB: set version in .local/.env"

