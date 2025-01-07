#!/usr/bin/env python3
import json
import sys
import urllib
from glob import glob
from typing import List, Dict

from loguru import logger
from textrepo.client import TextRepoClient

import untanngle.annotations as ann
import untanngle.camel_casing as cc
import untanngle.textfabric as tf
from untanngle.utils import add_segmented_text_type_if_missing

project_name = 'translatin'


@logger.catch()
def main(version: str):
    config = tf.TFUntangleConfig(
        project_name=project_name,
        data_path=f'data/{project_name}/{version}/prod',
        export_path=f'out',
        textrepo_base_uri=f'https://{project_name}.tt.di.huc.knaw.nl/textrepo',
        excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk", "tf:Entity"],
        tier0_type='tei:Work'
    )
    tf.untangle_tf_export(config)


@logger.catch()
def main0(version: str):
    basedir = f'data/{project_name}/{version}'
    textrepo_url = f"https://{project_name}.tt.di.huc.knaw.nl/textrepo"
    export_path = f"out/{project_name}/web_annotations.json"
    anno2node_path = f"{basedir}/anno2node.tsv"

    trc = TextRepoClient(base_uri=textrepo_url, verbose=True)
    add_segmented_text_type_if_missing(trc)

    manifestations_table_path = 'data/translatin-tables/manifestations.tsv'
    # manifestation_metadata_idx = load_manifestation_metadata(manifestations_table_path)

    for _dir in glob(f"{basedir}/*/"):
        base = _dir.split('/')[-2]
        anno_file_path = f'{_dir}anno-1.json'
        text_file_path = f'{_dir}text-0.json'

        logger.info(f"<= {text_file_path}")
        tr_version_id = upload_segmented_text(base, text_file_path, trc)

        logger.info(f"<= {anno_file_path}")
        web_annotations = tf.convert(project=f'translatin:{base}', anno_files=[anno_file_path],
                                     text_files=[text_file_path], anno2node_path=anno2node_path,
                                     textrepo_url=textrepo_url, textrepo_file_versions=tr_version_id)
        extended_annotations = add_image_targets(web_annotations)
        translatin_web_annotations = update_manifestation_annotations(extended_annotations)

        logger.info(f"=> {export_path}")
        with open(export_path, 'w') as f:
            json.dump(translatin_web_annotations, fp=f, indent=4, ensure_ascii=False)


def with_image_targets(annotation: Dict[str, any], iiif_url: str = None) -> (Dict[str, any], str):
    id_key = 'tei:id'
    metadata = annotation['body']['metadata']
    if "h" in metadata:
        x = int(metadata.pop('x', '0'))
        y = int(metadata.pop('y', '0'))
        w = int(metadata.pop('w', '0'))
        h = int(metadata.pop('h', '0'))
        if id_key in metadata:
            _id = metadata[id_key]
            if _id.endswith('.jpg'):
                encoded_id = urllib.parse.quote_plus(_id)
                iiif_url = f'https://iiif.huc.knaw.nl/translatin/{encoded_id}'
        itargets = [
            ann.simple_image_target(
                iiif_url=iiif_url,
                xywh=f'{x},{y},{w},{h}'
            ),
            ann.image_target(
                iiif_url=iiif_url,
                image_coords_list=ann.as_image_coords_list(x, y, w, h),
                coords_list=ann.as_coords_list(x, y, w, h)
            )
        ]

        annotation['target'].extend(itargets)
    return annotation, iiif_url


def add_image_targets(web_annotations: List[Dict[str, any]]) -> List[Dict[str, any]]:
    new_annotations = []
    iiif_url = None
    for a in web_annotations:
        new_annotation, iiif_url = with_image_targets(a, iiif_url=iiif_url)
        new_annotations.append(new_annotation)
    return new_annotations


if __name__ == '__main__':
    main(sys.argv[1])
