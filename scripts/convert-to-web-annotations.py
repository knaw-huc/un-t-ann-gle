#!/usr/bin/env python3
import argparse
import json
import random
from itertools import groupby
from typing import List, Dict

from icecream import ic
from rdflib import Graph

from untanngle.annotations import AttendantAnnotation, AttendantsListAnnotation, ColumnAnnotation, \
    LineAnnotation, PageAnnotation, RepublicParagraphAnnotation, ResolutionAnnotation, ReviewedAnnotation, \
    ScanAnnotation, SessionAnnotation, TextRegionAnnotation

annotation_class_mapper = dict(
    attendant=AttendantAnnotation,
    attendance_list=AttendantsListAnnotation,
    column=ColumnAnnotation,
    line=LineAnnotation,
    page=PageAnnotation,
    republic_paragraph=RepublicParagraphAnnotation,
    resolution=ResolutionAnnotation,
    reviewed=ReviewedAnnotation,
    scan=ScanAnnotation,
    session=SessionAnnotation,
    text_region=TextRegionAnnotation
)


def as_web_annotation(annotation: dict) -> dict:
    try:
        a_type = annotation.get('type')
        a_class = annotation_class_mapper[a_type]
        return a_class.from_dict(annotation).as_web_annotation()
    except Exception as e:
        print("failing input json:")
        print(json.dumps(annotation))
        ic(annotation)
        print("failure:")
        raise e


def normalize_annotation(annotation: dict, scanpage_iiif: dict, textrepo_base_url: str) -> dict:
    resource_id = annotation.get('resource_id')
    if resource_id:
        annotation['resource_id'] = f"{textrepo_base_url}/task/find/{resource_id}/file/contents?type=anchor"
    if 'image_coords' in annotation and 'iiif_url' not in annotation and annotation['id'].startswith('NL'):
        prefix = annotation['id'][:25]
        iiif_url = scanpage_iiif.get(prefix)
        if iiif_url:
            annotation['iiif_url'] = iiif_url
    return annotation


def convert_annotations(annotations, scanpage_iiif_uri_map, textrepo_base_url: str):
    num_annotations = len(annotations)
    print(f'> converting {num_annotations} annotations...')
    web_annotations = [
        as_web_annotation(
            normalize_annotation(annotation, scanpage_iiif_uri_map, textrepo_base_url)
        )
        for annotation in annotations
    ]

    print()
    return web_annotations


def export_to_file(web_annotations):
    out_file = 'web_annotations.json'
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(web_annotations, out, indent=4)


def get_sample(web_annotations: List[Dict]) -> List[Dict]:
    sampled_types = set()
    sample = []
    random.shuffle(web_annotations)
    for a in web_annotations:
        a_type = a["body"]["type"]
        if a_type not in sampled_types:
            sampled_types.add(a_type)
            sample.append(a)
    return sample


def export_sample(web_annotations):
    out_file = 'sample.json'
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(get_sample(web_annotations), out, indent=4)


def print_example_conversions(annotations, scanpage_iiif: dict, textrepo_base_url: str):
    key_func = lambda a: a['label']
    grouped_annotations = groupby(sorted(annotations, key=key_func), key=key_func)
    for label, group in grouped_annotations:
        print(f"label: *{label}*")

        random_annotation = random.choice(list(group))
        print(f"original annotation:\n{{code}}\n{json.dumps(random_annotation, indent=2)}\n{{code}}")

        web_annotation = as_web_annotation(normalize_annotation(random_annotation, scanpage_iiif, textrepo_base_url))
        print(f"W3C Web annotation:\n{{code}}\n{json.dumps(web_annotation, indent=2)}\n{{code}}")

        jsonld = json.dumps(web_annotation)
        g = Graph()
        g.parse(data=jsonld, format="json-ld")
        ttl = g.serialize(format="ttl").strip()
        print(f"W3C Web annotation as turtle:\n{{code}}\n{ttl}\n{{code}}")

        print("----")


def convert(input_file: str, textrepo_base_url: str):
    print(f'> importing {input_file} ...')
    with open(input_file) as f:
        annotations = json.load(f)
    num_annotations = len(annotations)
    print(f'> {num_annotations} annotations loaded')

    web_annotations = convert_annotations(annotations, "", textrepo_base_url)

    export_to_file(web_annotations)
    export_sample(web_annotations)

    print('> done!')


def main():
    parser = argparse.ArgumentParser(
        description="Convert an un-t-ann-gle annotationstore file to a web annotations file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("inputfile",
                        help="The un-t-ann-gle annotationstore file to convert",
                        type=str)
    parser.add_argument("-t",
                        "--textrepo-base-url",
                        help="The base URL for the text repository",
                        type=str,
                        default='https://demorepo.tt.di.huc.knaw.nl',
                        metavar="textrepo_base_url")
    args = parser.parse_args()
    convert(args.inputfile, args.textrepo_base_url)


if __name__ == '__main__':
    main()