#!/usr/bin/env python3
import json

from untanngle.mondriaan import TFAnnotation, IAnnotation, as_web_annotation


def main():
    basedir = 'data/'

    textfile = basedir + 'mondriaan-text.txt'
    tf_tokens = read_tf_tokens(textfile)

    anno_file = basedir + "mondriaan-anno.tsv"
    tf_annotations = read_tf_annotations(anno_file)

    web_annotations = build_web_annotations(tf_annotations, tf_tokens)
    print(json.dumps(web_annotations, indent=2))


def read_tf_tokens(textfile):
    with open(textfile) as f:
        tokens = [l.strip('\n') for l in f.readlines()]
    return tokens


def read_tf_annotations(anno_file):
    tf_annotations = []
    with open(anno_file) as f:
        for l in f.readlines():
            parts = l.replace('\n', '').split('\t')
            tf_annotations.append(TFAnnotation(int(parts[0]), parts[1], parts[2], parts[3]))
    return tf_annotations


def build_web_annotations(tf_annotations, tokens):
    ia_idx = {}
    note_target = {}
    for a in [a for a in tf_annotations]:
        match a.type:
            case 'element':
                target = a.target
                if "-" in target:
                    parts = target.split('-')
                    start_anchor = int(parts[0])
                    end_anchor = int(parts[1])
                else:
                    start_anchor = int(target)
                    end_anchor = start_anchor
                text = "".join(tokens[start_anchor:end_anchor + 1])
                ia = IAnnotation(id=a.id, type=a.body, text=text, start_anchor=start_anchor, end_anchor=end_anchor)
                ia_idx[a.id] = ia
            case 'node':
                anno_id = int(a.target)
                if anno_id in ia_idx:
                    ia_idx[anno_id].tf_node = int(a.body)
            case 'mark':
                note_anno_id = int(a.target)
                element_anno_id = int(a.body)
                note_target[note_anno_id] = element_anno_id
            case 'attribute':
                element_anno_id = int(a.target)
                (k, v) = a.body.split('=', 1)
                ia_idx[element_anno_id].metadata[k] = v
            case 'anno':
                element_anno_id = int(a.target)
                ia_idx[element_anno_id].metadata["anno"] = a.body

    ia = sorted(ia_idx.values(),
                key=lambda anno: (anno.start_anchor * 100_000 + anno.end_anchor) * 100_000 + anno.tf_node)

    return [as_web_annotation(a) for a in ia]


if __name__ == '__main__':
    main()
