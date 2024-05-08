#!/usr/bin/env python3
import json
from itertools import groupby

from intervaltree import IntervalTree
from loguru import logger

types = ["COM", "ORG", "LOC"]
# types = ["COM", "ORG", "LOC", "HOE"]
base_path = "/Users/bram/workspaces/republic/republic-kotlin-tools/data"


@logger.catch
def main():
    ner_annos = []
    for t in types:
        path = f"{base_path}/{t}-annotations.json"
        with open(path) as f:
            ner_annos.extend(json.load(f))
    anno_groups = groupby(sorted(ner_annos, key=group_key), key=group_key)
    for label, group in anno_groups:
        print(label)
        it = IntervalTree()
        annos = list(group)
        for anno in annos:
            it[range_start(anno):range_end(anno)] = anno
        for anno in annos:
            enveloped_annos = [a.data for a in sorted(it.envelop(range_start(anno), range_end(anno))) if a.data != anno]
            if enveloped_annos:
                print(json.dumps(anno, indent=True))
                print(f"  {anno_id(anno)} ({anno['reference']['tag_text']}) envelops:")
                for ea in enveloped_annos:
                    print(json.dumps(ea, indent=True))
                    print(f"    {anno_id(ea)} ({ea['reference']['tag_text']})")
        print()


def group_key(x):
    return x["reference"]["paragraph_id"]


def range_start(anno) -> int:
    return int(anno["reference"]["offset"])


def range_end(anno) -> int:
    return int(anno["reference"]["end"])


def anno_id(anno) -> str:
    category = anno['entity']['category']
    name = anno['entity']['name'].replace(' ', '-')
    offset = range_start(anno)
    end = range_end(anno)
    return f"urn:republic:entity:{category}:{name}:{offset}-{end}".lower()


if __name__ == '__main__':
    main()
