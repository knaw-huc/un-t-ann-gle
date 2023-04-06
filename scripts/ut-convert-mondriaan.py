#!/usr/bin/env python3
import json

from untanngle.mondriaan import IAnnotation, as_web_annotation, TFAnnotation


def main():
    basedir = 'data'

    textfile = f'{basedir}/mondriaan-text.json'
    tf_tokens = read_tf_tokens(textfile)

    anno_file = f"{basedir}/mondriaan-anno.json"
    tf_annotations = read_tf_annotations(anno_file)
    web_annotations = build_web_annotations(tf_annotations, tf_tokens)
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


def build_web_annotations(tf_annotations, tokens):
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
                key=lambda anno: (anno.start_anchor * 100_000 + anno.end_anchor) * 100_000 + anno.tf_node)

    # TODO: convert ptr annotations to annotation linking the ptr target to the body.id of the m:Note with the corresponding id
    # TODO: convert rs annotations to annotation linking the rkd url in metadata.anno to the rd target
    # TODO: convert pb annotations to page annotations, from the <pb> to the next <pb> or </div>, with link to facs
    # TODO: convert ref annotations
    return [as_web_annotation(a, textrepo_url="https://mondriaan.tt.di.huc.knaw.nl/textrepo",
                              textrepo_version="9db547e7-1249-40f2-99ab-f014edac6cd1") for a in ia]


if __name__ == '__main__':
    main()
