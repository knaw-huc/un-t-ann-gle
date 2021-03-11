#!/usr/bin/env python3

import argparse
import json

from extractors import tei_extractor, json_extractor
from textservice import segmentedtext

TEI = 'tei'
REPUBLIC = 'republic'


def export1(text_segments: list, annotations: list):
    """
    export the text segment list and annotation list to 2 separate json files
    """
    text_file = open('text_segments.json', 'w')
    text_file.write(json.dumps(text_segments, indent=4, cls=segmentedtext.SegmentEncoder))
    text_file.write("\n")
    text_file.close()

    ann_file = open('annotations.json', 'w')
    ann_file.write(json.dumps(annotations, indent=4, cls=segmentedtext.AnchorEncoder))
    ann_file.write("\n")
    ann_file.close()


def export_to_text_repo(text_segments: list):
    pass


def export_to_annotation_server(annotations: list):
    pass


def export(text_segments: list, annotations: list):
    export_to_text_repo(text_segments)
    export_to_annotation_server(annotations)


def main():
    print("Welcome to un-t-ann-gle!")
    parser = argparse.ArgumentParser(
        description='untanngle splits rich text files (json/xml) into bare text segments and annotations.')
    parser.add_argument('sourcefile_path', nargs='+', help='the path(s) to the source file(s)')
    parser.add_argument('-t', '--type', required=True, choices=[REPUBLIC, TEI], dest='source_type',
                        help='the type of the source file(s)')
    args = parser.parse_args()
    source_paths = args.sourcefile_path
    source_type = args.source_type
    if source_type == TEI:
        print('parsing tei...')
        (text_segments, annotations) = tei_extractor.process(source_paths)
    elif source_type == REPUBLIC:
        print('parsing REPUBLIC json...')
        (text_segments, annotations) = json_extractor.process(source_paths)
    export(text_segments, annotations)


if __name__ == '__main__':
    main()
