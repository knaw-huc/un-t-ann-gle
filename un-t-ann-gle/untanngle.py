#!/usr/bin/env python3

import argparse
import json


def tei_extract(source: str) -> (list, list):
    return (["segment1", "segment2"], ["ann1", "ann2"])


def json_extract(source: str) -> (list, list):
    return (["segment1", "segment2"], ["ann1", "ann2"])


def export(text_segments: list, annotations: list):
    text_file = open('text_segments.json', 'w')
    text_file.write(json.dumps(text_segments))
    text_file.write("\n")
    text_file.close()

    ann_file = open('annotations.json', 'w')
    ann_file.write(json.dumps(annotations))
    ann_file.write("\n")
    ann_file.close()


def do_tei_extract(source: str):
    print('parsing tei...')
    (text_segments, annotations) = tei_extract(source)
    export(text_segments, annotations)


def do_json_extract(source: str):
    print('parsing json...')
    (text_segments, annotations) = json_extract(source)
    export(text_segments, annotations)


def main():
    print("Welcome to un-t-ann-gle!")
    parser = argparse.ArgumentParser(
        description='un-t-ann-gle splits rich text files (json/xml) into bare text segments and annotations.')
    parser.add_argument('source')
    args = parser.parse_args()
    source_filename = args.source
    source_file = open(source_filename, 'r')
    source = source_file.read()
    source_file.close()
    if (source_filename.lower().endswith('.xml')):
        do_tei_extract(source)
    elif (source_filename.lower().endswith('.json')):
        do_json_extract(source)
    else:
        raise Exception("Sorry, I don't know how to parse {}".format(source_filename))


if __name__ == '__main__':
    main()
