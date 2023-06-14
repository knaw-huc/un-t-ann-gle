#!/usr/bin/env python3
import argparse
import csv
import json
import random
from itertools import groupby
from typing import List, Dict

from icecream import ic
from loguru import logger
from rdflib import Graph

from untanngle.annotations import AttendantAnnotation, AttendantsListAnnotation, ColumnAnnotation, \
    LineAnnotation, PageAnnotation, RepublicParagraphAnnotation, ResolutionAnnotation, ReviewedAnnotation, \
    ScanAnnotation, SessionAnnotation, TextRegionAnnotation, VolumeAnnotation

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


def as_web_annotation(annotation: dict, textrepo_url: str, version_id: str, canvas_idx: dict) -> dict:
    try:
        a_type = annotation.get('type')
        a_class = annotation_class_mapper[a_type]
        return a_class.from_dict(annotation).as_web_annotation(textrepo_base_url=textrepo_url, version_id=version_id,
                                                               canvas_idx=canvas_idx)
    except Exception as e:
        print("failing input json:")
        print(json.dumps(annotation))
        ic(annotation)
        print("failure:")
        raise e


def normalize_annotation(annotation: dict, scanpage_iiif: dict) -> dict:
    if 'image_coords' in annotation and 'iiif_url' not in annotation and annotation['id'].startswith('NL'):
        prefix = annotation['id'][:25]
        iiif_url = scanpage_iiif.get(prefix)
        if iiif_url:
            annotation['iiif_url'] = iiif_url
    if annotation["type"] == "scan":
        opening = int(annotation["id"].split("_")[-1])
        annotation["metadata"] = {
            "type": "tt:ScanMetadata",
            "volume": "1728",
            "opening": opening
        }
    return annotation


def convert_annotations(annotations, scanpage_iiif_uri_map, textrepo_url: str, version_id: str, canvas_idx):
    num_annotations = len(annotations)
    print(f'> converting {num_annotations} annotations...')
    web_annotations = [
        as_web_annotation(
            normalize_annotation(annotation, scanpage_iiif_uri_map),
            textrepo_url, version_id, canvas_idx
        )
        for annotation in annotations
    ]
    print()
    return web_annotations


def export_to_file(web_annotations, export_path: str):
    out_file = f"{export_path}/web_annotations.json"
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(web_annotations, out, indent=4, ensure_ascii=False)


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


def export_sample(web_annotations, export_path: str):
    out_file = f'{export_path}/sample.json'
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(get_sample(web_annotations), out, indent=4, ensure_ascii=False)


def print_example_conversions(annotations, scanpage_iiif: dict, textrepo_base_url: str):
    def annotation_label(a):
        return a['label']

    grouped_annotations = groupby(sorted(annotations, key=annotation_label), key=annotation_label)
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


def create_document_annotation(end_anchor: int, title: str, textrepo_base_url: str, version_id: str):
    da = VolumeAnnotation(title=title,
                          begin_anchor=0, end_anchor=end_anchor,
                          manifest_url="https://images.diginfra.net/api/pim/imageset/67533019-4ca0-4b08-b87e-fd5590e7a077/manifest")
    return da.as_web_annotation(textrepo_base_url=textrepo_base_url, version_id=version_id)


def convert(input_file: str, textrepo_url: str, version_id: str, canvas_index_file: str, export_path: str) -> None:
    print(f'> importing {input_file} ...')
    with open(input_file) as f:
        annotations = json.load(f)
    num_annotations = len(annotations)
    print(f'> {num_annotations} annotations loaded')

    end_anchor = max(a["end_anchor"] for a in annotations)
    document_annotation = create_document_annotation(end_anchor=end_anchor, title="1728",
                                                     textrepo_base_url=textrepo_url,
                                                     version_id=version_id)

    canvas_idx = read_canvas_idx(canvas_index_file)
    web_annotations = convert_annotations(annotations, "", textrepo_url, version_id, canvas_idx)

    web_annotations.append(document_annotation)

    export_to_file(web_annotations, export_path)
    export_sample(web_annotations, export_path)

    print('> done!')


def read_canvas_idx(path: str) -> Dict[str, str]:
    idx = {}
    with open(path) as f:
        for line in csv.reader(f):
            idx[line[0]] = line[1]
    return idx


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert an un-t-ann-gle annotationstore file to a web annotations file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("inputfile",
                        help="The un-t-ann-gle annotationstore file to convert",
                        type=str)
    parser.add_argument("-t",
                        "--textrepo-base-url",
                        required=True,
                        help="The base URL of the TextRepo server containing the text the annotations refer to "
                             "( example: "
                             "https://textrepo.republic-caf.diginfra.org/api/ )",
                        type=str,
                        metavar="textrepo_base_url")
    parser.add_argument("-v",
                        "--version-id",
                        required=True,
                        help="The versionId of the text the annotations refer to "
                             "( example: "
                             "42df1275-81cd-489c-b28c-345780c3889b )",
                        type=str,
                        metavar="version_id")
    parser.add_argument("-c",
                        "--canvas-index",
                        required=True,
                        help="A csv file linking image urls to the corresponding canvas url",
                        type=str,
                        metavar="canvas_index_file")
    parser.add_argument("-o",
                        "--output-directory",
                        required=True,
                        help="The directory to put the output files into",
                        type=str)
    args = parser.parse_args()
    return args


@logger.catch
def main():
    args = parse_args()
    if args.textrepo_base_url.endswith('/'):
        args.textrepo_base_url = args.textrepo_base_url[0:-1]
    convert(args.inputfile, args.textrepo_base_url, args.version_id, args.canvas_index, args.output_directory)


if __name__ == '__main__':
    main()
