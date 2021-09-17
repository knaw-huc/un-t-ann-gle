#!/usr/bin/env python3

import json
import random
import sys
from itertools import groupby

from rdflib import Graph

from untanngle.annotations import LineAnnotation, AttendantAnnotation, AttendantsListAnnotation, ColumnAnnotation, \
    ResolutionAnnotation, ScanPageAnnotation, SessionAnnotation, TextRegionAnnotation


def scanpage_as_web_annotation(annotation: dict) -> dict:
    return ScanPageAnnotation.from_dict(annotation).as_web_annotation()


def column_as_web_annotation(annotation: dict) -> dict:
    return ColumnAnnotation.from_dict(annotation).as_web_annotation()


def textregion_as_web_annotation(annotation: dict) -> dict:
    return TextRegionAnnotation.from_dict(annotation).as_web_annotation()


def line_as_web_annotation(annotation: dict) -> dict:
    return LineAnnotation.from_dict(annotation).as_web_annotation()


def session_as_web_annotation(annotation: dict) -> dict:
    return SessionAnnotation.from_dict(annotation).as_web_annotation()


def attendantslist_as_web_annotation(annotation: dict) -> dict:
    return AttendantsListAnnotation.from_dict(annotation).as_web_annotation()


def attendant_as_web_annotation(annotation: dict) -> dict:
    return AttendantAnnotation.from_dict(annotation).as_web_annotation()


def resolution_as_web_annotation(annotation: dict) -> dict:
    return ResolutionAnnotation.from_dict(annotation).as_web_annotation()


annotation_mapper = {
    'scanpage': scanpage_as_web_annotation,
    'columns': column_as_web_annotation,
    'textregions': textregion_as_web_annotation,
    'lines': line_as_web_annotation,
    'sessions': session_as_web_annotation,
    'attendantslists': attendantslist_as_web_annotation,
    'attendants': attendant_as_web_annotation,
    'resolutions': resolution_as_web_annotation
}


def as_web_annotation(annotation: dict) -> dict:
    # ic(annotation)
    label = annotation.get('label')
    return annotation_mapper[label](annotation)


def normalize_annotation(annotation: dict, scanpage_iiif) -> dict:
    resource_id = annotation.get('resource_id')
    if resource_id:
        annotation['resource_id'] = f"https://demorepo.tt.di.huc.knaw.nl/task/find/{resource_id}/contents"
    if 'image_coords' in annotation and 'iiif_url' not in annotation and annotation['id'].startswith('NL'):
        prefix = annotation['id'][:25]
        iiif_url = scanpage_iiif.get(prefix)
        if iiif_url:
            annotation['iiif_url'] = iiif_url
    return annotation


def convert_annotations(annotations, scanpage_iiif_uri_map):
    num_annotations = len(annotations)
    print(f'> converting {num_annotations} annotations...')
    web_annotations = [
        as_web_annotation(
            normalize_annotation(annotation, scanpage_iiif_uri_map)
        )
        for i, annotation in enumerate(annotations)
    ]

    print()
    return web_annotations


def export_to_file(web_annotations):
    out_file = 'web_annotations.json'
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(web_annotations, out, indent=4)


def print_example_conversions(annotations, scanpage_iiif: dict):
    key_func = lambda a: a['label']
    grouped_annotations = groupby(sorted(annotations, key=key_func), key=key_func)
    for label, group in grouped_annotations:
        print(f"label: *{label}*")

        random_annotation = random.choice(list(group))
        print(f"original annotation:\n{{code}}\n{json.dumps(random_annotation, indent=2)}\n{{code}}")

        web_annotation = as_web_annotation(normalize_annotation(random_annotation, scanpage_iiif))
        print(f"W3C Web annotation:\n{{code}}\n{json.dumps(web_annotation, indent=2)}\n{{code}}")

        jsonld = json.dumps(web_annotation)
        g = Graph()
        g.parse(data=jsonld, format="json-ld")
        ttl = g.serialize(format="ttl").strip()
        print(f"W3C Web annotation as turtle:\n{{code}}\n{ttl}\n{{code}}")

        print("----")


def convert(input: str):
    print(f'> importing {input} ...')
    with open(input) as f:
        annotations = json.load(f)
    num_annotations = len(annotations)
    print(f'> {num_annotations} annotations loaded')

    scanpage_iiif_uri_map = {a['scan_id']: a['iiif_url'] for a in annotations if a['label'] == 'scanpage'}
    # ic(scanpage_iiif_uri_map)

    # print_example_conversions(annotations, scanpage_iiif_uri_map)

    web_annotations = convert_annotations(annotations, scanpage_iiif_uri_map)

    export_to_file(web_annotations)

    print('> done!')


if __name__ == '__main__':
    convert(sys.argv[1])
