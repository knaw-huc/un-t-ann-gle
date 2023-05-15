#!/usr/bin/env python3
import json
from typing import List

from icecream import ic
from loguru import logger

from untanngle.mondriaan import IAnnotation, TFAnnotation, AnnotationTransformer


@logger.catch()
def main():
    basedir = 'data'

    textfile = f'{basedir}/mondriaan-text.json'
    tf_tokens = read_tf_tokens(textfile)

    anno_file = f"{basedir}/mondriaan-anno.json"
    tf_annotations = read_tf_annotations(anno_file)
    web_annotations = build_web_annotations(tf_annotations, tf_tokens)
    # selection = [w for w in web_annotations if w["body"]["type"] in ("tei:Pb", "tei:Div")]
    # print(json.dumps(selection, indent=2))
    print(json.dumps(web_annotations, indent=2))


def read_tf_tokens(textfile):
    with open(textfile) as f:
        contents = json.load(f)
    return contents["_ordered_segments"]


def read_tf_annotations(anno_file):
    tf_annotations = []
    with open(anno_file) as f:
        content = json.load(f)
        for _id, properties in content.items():
            tf_annotations.append(TFAnnotation(id=_id, type=properties[0], body=properties[1], target=properties[2]))
    return tf_annotations


def modify_pb_annotations(ia: List[IAnnotation], tokens) -> List[IAnnotation]:
    pb_end_anchor = 0
    last_page_in_div = None
    for i, a in enumerate(ia):
        if is_div_with_pb(a):
            pb_end_anchor = a.end_anchor
            last_page_in_div = None
        elif a.type == "pb":
            if pb_end_anchor > a.start_anchor:
                a.end_anchor = pb_end_anchor
            else:
                logger.warning(f"<pb> outside of <div>: {a}")
            if not last_page_in_div:
                last_page_in_div = i
            else:
                prev = ia[last_page_in_div]
                prev.end_anchor = a.start_anchor - 1
                prev.text = text_of(prev, tokens)
            a.type = 'page'
            a.text = text_of(a, tokens)
    return ia


def text_of(a, tokens):
    return "".join(tokens[a.start_anchor:a.end_anchor + 1])


def is_div_with_pb(a):
    return a.type == "div" \
        and "type" in a.metadata \
        and a.metadata["type"] in ("original", "translation", "postalData")


def sanity_check(ia: List[IAnnotation]):
    annotations_with_invalid_anchor_range = [a for a in ia if a.start_anchor > a.end_anchor]
    if annotations_with_invalid_anchor_range:
        logger.error("There are annotations with invalid anchor range:")
        ic(annotations_with_invalid_anchor_range)

    letter_annotations = [a for a in ia if a.type == 'letter']
    for i in range(len(letter_annotations)):
        for j in range(i + 1, len(letter_annotations)):
            anno1 = letter_annotations[i]
            anno2 = letter_annotations[j]
            if annotations_overlap(anno1, anno2):
                logger.error("Overlapping Letter annotations: ")
                ic(anno1.id, anno1.metadata, anno1.start_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.start_anchor, anno2.end_anchor)

    sentence_annotations = [a for a in ia if a.type == 'letter']
    for i in range(len(sentence_annotations)):
        for j in range(i + 1, len(sentence_annotations)):
            anno1 = sentence_annotations[i]
            anno2 = letter_annotations[j]
            if annotations_overlap(anno1, anno2):
                logger.error("Overlapping Letter annotations: ")
                ic(anno1.id, anno1.metadata, anno1.start_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.start_anchor, anno2.end_anchor)


def annotations_overlap(anno1, anno2):
    return (anno1.end_anchor - 1) >= anno2.start_anchor


def build_web_annotations(tf_annotations, tokens):
    at = AnnotationTransformer(textrepo_url="https://mondriaan.tt.di.huc.knaw.nl/textrepo",
                               textrepo_version="c637abd5-7e07-4a3d-962e-fb40d4656ec4")
    ia_idx = {}
    note_target = {}
    for a in [a for a in tf_annotations]:
        match a.type:
            case 'element':
                target = a.target
                parts = target.split('-')
                start_anchor = int(parts[0])
                end_anchor = int(parts[1])
                text = "".join(tokens[start_anchor:end_anchor])
                ia = IAnnotation(id=a.id, type=a.body, text=text, start_anchor=start_anchor, end_anchor=end_anchor - 1)
                ia_idx[a.id] = ia
            case 'node':
                anno_id = a.target
                if anno_id in ia_idx:
                    ia_idx[anno_id].tf_node = int(a.body)
                # else:
                #     ic(a)
            case 'mark':
                note_anno_id = a.target
                if note_anno_id in ia_idx:
                    element_anno_id = int(a.body)
                    note_target[note_anno_id] = element_anno_id
                # else:
                #     ic(a)
            case 'attribute':
                element_anno_id = a.target
                if element_anno_id in ia_idx:
                    (k, v) = a.body.split('=', 1)
                    ia_idx[element_anno_id].metadata[k] = v
                # else:
                #     ic(a)
            case 'anno':
                element_anno_id = a.target
                if element_anno_id in ia_idx:
                    ia_idx[element_anno_id].metadata["anno"] = a.body
                # else:
                #     ic(a)

    ia = sorted(ia_idx.values(),
                key=lambda anno: (anno.start_anchor * 100_000 + (1000 - anno.end_anchor)) * 100_000 + anno.tf_node)

    ia = modify_pb_annotations(ia, tokens)

    # TODO: convert ptr annotations to annotation linking the ptr target to the body.id of the m:Note with the corresponding id
    # TODO: convert rs annotations to annotation linking the rkd url in metadata.anno to the rd target
    # TODO: convert ref annotations

    sanity_check(ia)
    return [at.as_web_annotation(a) for a in ia]


if __name__ == '__main__':
    main()
