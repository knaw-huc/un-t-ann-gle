#!/usr/bin/env python3

import argparse
import json

from extractors import tei_extractor, json_extractor

TEI = 'tei'
REPUBLIC = 'republic'


def export(text_segments: list, annotations: list):
    text_file = open('text_segments.json', 'w')
    text_file.write(json.dumps(text_segments._ordered_segments))
    text_file.write("\n")
    text_file.close()

    ann_file = open('annotations.json', 'w')
    ann_file.write(json.dumps(annotations))
    ann_file.write("\n")
    ann_file.close()


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
        export(text_segments, annotations)
    elif source_type == REPUBLIC:
        print('parsing REPUBLIC json...')
        (text_segments, annotations) = json_extractor.process(source_paths)
        export(text_segments, annotations)


if __name__ == '__main__':
    main()
