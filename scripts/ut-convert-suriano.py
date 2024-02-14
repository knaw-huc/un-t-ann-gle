#!/usr/bin/env python3
import glob
import itertools
import json
import time
from typing import List, Dict, Any

from loguru import logger
from textrepo.client import TextRepoClient

import untanngle.textfabric as tf

basedir = 'data/suriano/0.0.3'
textfile = f'{basedir}/text.json'
anno_files = sorted(glob.glob(f"{basedir}/anno-*.json"))
textrepo_base_uri = "https://suriano.tt.di.huc.knaw.nl/textrepo"
external_id = "suriano"


def main():
    start = time.perf_counter()
    textrepo_file_version = upload_to_tr(textfile)
    web_annotations = tf.convert(project=external_id,
                                 anno_files=anno_files,
                                 text_file=textfile,
                                 textrepo_url=textrepo_base_uri,
                                 textrepo_file_version=textrepo_file_version)
    logger.info(f"{len(web_annotations)} annotations")
    export_path = "out/suriano-web_annotations.json"
    logger.info(f"=> {export_path}")
    with open(export_path, "w") as f:
        json.dump(obj=web_annotations, fp=f, indent=2)
    show_annotation_counts(web_annotations)
    end = time.perf_counter()
    print(f"untangling took {end - start:0.4f} seconds")


def upload_to_tr(tf_text_file: str) -> str:
    trc = TextRepoClient(textrepo_base_uri, verbose=True)
    with open(tf_text_file) as f:
        content = f.read()
    # trc.create_document(external_id)
    check_file_types(trc)
    version_id = trc.import_version(external_id=external_id,
                                    type_name='segmented_text',
                                    contents=content,
                                    as_latest_version=True)
    return version_id.version_id


def check_file_types(client: TextRepoClient):
    name = "segmented_text"
    available_type_names = [t.name for t in client.read_file_types()]
    if name not in available_type_names:
        client.create_file_type(name=name, mimetype="application/json")


def show_annotation_counts(web_annotations: List[Dict[str, Any]]):
    print()
    print("Annotation types:")
    typed_annotations = [a for a in web_annotations if "type" in a["body"]]
    typed_annotations.sort(key=lambda a: a['body']['type'])
    grouped = itertools.groupby(typed_annotations, lambda a: a['body']['type'])
    counts = []
    for type, anno_group in grouped:
        counts.append([type, len([a for a in anno_group])])
    counts.sort(key=lambda t: t[1])
    max_type_name_size = max([len(t[0]) for t in counts])
    for t in counts:
        print(f"{t[0]:{max_type_name_size}}: {t[1]}")
    print()


if __name__ == '__main__':
    main()
