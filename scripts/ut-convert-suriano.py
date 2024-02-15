#!/usr/bin/env python3
import glob
import itertools
import json
import time
from typing import List, Dict, Any

from loguru import logger
from textrepo.client import TextRepoClient

import untanngle.textfabric as tf
from untanngle.utils import trc_has_document_with_external_id

basedir = 'data/suriano/0.0.4'
text_files = sorted(glob.glob(f'{basedir}/text-*.json'))
anno_files = sorted(glob.glob(f"{basedir}/anno-*.json"))
textrepo_base_uri = "https://suriano.tt.di.huc.knaw.nl/textrepo"
project_name = "suriano"
export_path = "out/suriano-web_annotations.json"


@logger.catch()
def main():
    start = time.perf_counter()
    textrepo_file_version = upload_to_tr(text_files)
    web_annotations = tf.convert(project=project_name,
                                 anno_files=anno_files,
                                 text_files=text_files,
                                 textrepo_url=textrepo_base_uri,
                                 textrepo_file_versions=textrepo_file_version)
    logger.info(f"{len(web_annotations)} annotations")

    store_web_annotations(web_annotations)

    print(f"text files: {len(text_files)}")

    show_annotation_counts(web_annotations)
    end = time.perf_counter()
    print(f"untangling took {end - start:0.4f} seconds")


def upload_to_tr(tf_text_files: List[str]) -> Dict[str, str]:
    trc = TextRepoClient(textrepo_base_uri, verbose=True)
    check_file_types(trc)
    versions = {}
    for tf_text_file in tf_text_files:
        file_num = tf.get_file_num(tf_text_file)
        external_id = f"{project_name}-{file_num}"
        logger.info(f"<= {tf_text_file}")
        with open(tf_text_file) as f:
            content = f.read()
        if not trc_has_document_with_external_id(trc, external_id):
            trc.create_document(external_id)
        version_id = trc.import_version(external_id=external_id,
                                        type_name='segmented_text',
                                        contents=content,
                                        as_latest_version=True)
        versions[file_num] = version_id.version_id
    return versions


def check_file_types(client: TextRepoClient):
    name = "segmented_text"
    available_type_names = [t.name for t in client.read_file_types()]
    if name not in available_type_names:
        client.create_file_type(name=name, mimetype="application/json")


def store_web_annotations(web_annotations):
    logger.info(f"=> {export_path}")
    with open(export_path, "w") as f:
        json.dump(obj=web_annotations, fp=f, indent=2)


def show_annotation_counts(web_annotations: List[Dict[str, Any]]):
    print()
    print("Annotation types:")
    typed_annotations = [a for a in web_annotations if "type" in a["body"]]
    typed_annotations.sort(key=lambda a: a['body']['type'])
    grouped = itertools.groupby(typed_annotations, lambda a: a['body']['type'])
    counts = []
    for atype, anno_group in grouped:
        counts.append([atype, len([a for a in anno_group])])
    counts.sort(key=lambda t: t[1])
    max_type_name_size = max([len(t[0]) for t in counts])
    for t in counts:
        print(f"{t[0]:{max_type_name_size}}: {t[1]}")
    print()


if __name__ == '__main__':
    main()
