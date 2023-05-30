import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List

from icecream import ic
from loguru import logger


@dataclass
class TFAnnotation:
    id: str
    namespace: str
    type: str
    body: str
    target: str


@dataclass
class IAnnotation:
    id: str = ""
    namespace: str = ""
    type: str = ""
    tf_node: int = 0
    text: str = ""
    start_anchor: int = 0
    end_anchor: int = 0
    metadata: Dict[str, any] = field(default_factory=dict)


def as_class_name(string: str) -> str:
    return string[0].capitalize() + string[1:]


@dataclass
class AnnotationTransformer:
    textrepo_url: str
    textrepo_version: str

    def as_web_annotation(self, ia: IAnnotation) -> Dict[str, Any]:
        body_type = f"{ia.namespace}:{as_class_name(ia.type)}"
        anno = {
            "@context": [
                "http://www.w3.org/ns/anno.jsonld",
                {
                    "nlp": "https://ns.tt.di.huc.knaw.nl/nlp",
                    "tf": "https://ns.tt.di.huc.knaw.nl/tf",
                    "tt": "https://ns.tt.di.huc.knaw.nl/tt",
                    "tei": "https://ns.tt.di.huc.knaw.nl/tei"
                }
            ],
            "type": "Annotation",
            "purpose": "tagging",
            "generated": datetime.today().isoformat(),
            "body": {
                "id": f"urn:mondriaan:{ia.type}:{ia.tf_node}",
                "type": body_type,
                "tf:textfabric_node": ia.tf_node,
                "text": ia.text
            },
            "target": [
                {
                    "source": f"{self.textrepo_url}/rest/versions/{self.textrepo_version}/contents",
                    "type": "Text",
                    "selector": {
                        "type": "tt:TextAnchorSelector",
                        "start": ia.start_anchor,
                        "end": ia.end_anchor
                    }
                },
                {
                    "source": (
                        f"{self.textrepo_url}/view/versions/{self.textrepo_version}/segments/index/{ia.start_anchor}/{ia.end_anchor}"),
                    "type": "Text"
                }
            ]
        }
        if ia.metadata:
            anno["body"]["metadata"] = {f"{k}": v for k, v in ia.metadata.items()}
        if ia.type == "letter":
            anno["body"]["metadata"]["folder"] = "proeftuin"
            anno["target"].append({
                "source": "https://images.diginfra.net/iiif/NL-HaNA_1.01.02%2F3783%2FNL-HaNA_1.01.02_3783_0002.jpg/full/full/0/default.jpg",
                "type": "Image"
            })
        if ia.type == "folder":
            anno["body"]["metadata"]["manifest"] = \
                "https://images.diginfra.net/api/pim/imageset/67533019-4ca0-4b08-b87e-fd5590e7a077/manifest"
            anno["body"].pop("text")
        else:
            canvas_target = {
                "@context": "https://brambg.github.io/ns/republic.jsonld",
                "source": "https://images.diginfra.net/api/pim/iiif/67533019-4ca0-4b08-b87e-fd5590e7a077/canvas/20633ef4-27af-4b13-9ffe-dfc0f9dad1d7",
                "type": "Canvas"
            }
            anno["target"].append(canvas_target)
        return anno


def convert(anno_file: str, text_file: str, textrepo_url: str, textrepo_file_version: str):
    tf_tokens = read_tf_tokens(text_file)
    tf_annotations = read_tf_annotations(anno_file)
    web_annotations = build_web_annotations(tf_annotations=tf_annotations, tokens=tf_tokens, textrepo_url=textrepo_url,
                                            textrepo_file_version=textrepo_file_version)
    return web_annotations


def read_tf_tokens(textfile):
    with open(textfile) as f:
        contents = json.load(f)
    return contents["_ordered_segments"]


def read_tf_annotations(anno_file):
    tf_annotations = []
    with open(anno_file) as f:
        content = json.load(f)
        for _id, properties in content.items():
            tf_annotations.append(TFAnnotation(id=_id, type=properties[0], namespace=properties[1], body=properties[2],
                                               target=properties[3]))
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


def build_web_annotations(tf_annotations, tokens, textrepo_url: str, textrepo_file_version: str):
    at = AnnotationTransformer(textrepo_url=textrepo_url,
                               textrepo_version=textrepo_file_version)
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
                ia = IAnnotation(id=a.id, namespace=a.namespace, type=a.body, text=text,
                                 start_anchor=start_anchor,
                                 end_anchor=end_anchor - 1)
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
            case 'format':
                pass
            case 'pi':
                pass
            case 'edge':
                pass
            case _:
                logger.warning(f"unhandled type: {a.type}")

    ia = sorted(ia_idx.values(),
                key=lambda anno: (anno.start_anchor * 100_000 + (1000 - anno.end_anchor)) * 100_000 + anno.tf_node)

    ia = modify_pb_annotations(ia, tokens)

    # TODO: convert ptr annotations to annotation linking the ptr target to the body.id of the m:Note with the corresponding id
    # TODO: convert rs annotations to annotation linking the rkd url in metadata.anno to the rd target
    # TODO: convert ref annotations

    sanity_check(ia)
    return [at.as_web_annotation(a) for a in ia]
