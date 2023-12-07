#!/usr/bin/env python3
import json
from glob import glob
from typing import List, Dict

from loguru import logger
from textrepo.client import TextRepoClient

import untanngle.annotations as ANN
from untanngle import textfabric


def upload_segmented_text(external_id: str, text_file_path: str, client: TextRepoClient) -> str:
    with open(text_file_path) as f:
        content = f.read()
    version_id = client.import_version(external_id=external_id,
                                       type_name='segmented_text',
                                       contents=content,
                                       as_latest_version=True)
    return version_id.version_id


def check_file_types(client: TextRepoClient):
    name = "segmented_text"
    available_type_names = [t.name for t in client.read_file_types()]
    if name not in available_type_names:
        client.create_file_type(name=name, mimetype="application/json")


def with_image_targets(annotation: Dict[str, any], iiif_url: str = None) -> (Dict[str, any], str):
    metadata = annotation['body']['metadata']
    if "h" in metadata:
        x = int(metadata.pop('x', '0'))
        y = int(metadata.pop('y', '0'))
        w = int(metadata.pop('w', '0'))
        h = int(metadata.pop('h', '0'))
        if 'id' in metadata:
            _id = metadata['id']
            if _id.endswith('.jpg'):
                iiif_url = f'https://iiif.huc.knaw.nl/translatin/{_id}'
        itargets = [
            ANN.simple_image_target(
                iiif_url=iiif_url,
                xywh=f'{x},{y},{w},{h}'
            ),
            ANN.image_target(
                iiif_url=iiif_url,
                image_coords_list=ANN.as_image_coords_list(x, y, w, h),
                coords_list=ANN.as_coords_list(x, y, w, h)
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


@logger.catch()
def main():
    basedir = 'data/translatin'
    textrepo_url = "https://translatin.tt.di.huc.knaw.nl/textrepo"
    trc = TextRepoClient(base_uri=textrepo_url, verbose=True)
    check_file_types(trc)

    for dir in glob(f"{basedir}/*/"):
        base = dir.split('/')[-2]
        anno_file_path = f'{dir}anno.json'
        text_file_path = f'{dir}text.json'
        logger.info(f"<= {text_file_path}")
        tr_version_id = upload_segmented_text(base, text_file_path, trc)
        logger.info(f"<= {anno_file_path}")
        web_annotations = textfabric.convert(project=f'translatin:{base}',
                                             anno_file=anno_file_path,
                                             text_file=text_file_path,
                                             textrepo_url=textrepo_url,
                                             textrepo_file_version=tr_version_id)
        translatin_web_annotations = add_image_targets(web_annotations)
        export_path = f"out/translatin-{base}-web_annotations.json"
        logger.info(f"=> {export_path}")
        with open(export_path, 'w') as f:
            json.dump(translatin_web_annotations, fp=f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    main()
