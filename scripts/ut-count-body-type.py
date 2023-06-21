#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict

from loguru import logger


def process(path: str):
    with open(path) as f:
        annotations = json.load(f)
    counts = defaultdict(int)
    for a in annotations:
        if "body" in a:
            a_type = a["body"]["type"]
        else:
            a_type = a["type"]
        counts[a_type] += 1
    max_key_length = max(len(key) for key in counts.keys())
    max_count_length = max(len(str(val)) for val in counts.values())
    for _type in sorted(counts.keys()):
        print(f"{_type:{max_key_length + 1}}: {counts[_type]:{max_count_length}}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read the given json file with annotations, and count the annotations per body.type",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("inputfile",
                        help="The json file with the annotations",
                        type=str)
    args = parser.parse_args()
    return args


@logger.catch
def main():
    args = parse_args()
    process(args.inputfile)


if __name__ == '__main__':
    main()
