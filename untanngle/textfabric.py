import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List

from icecream import ic
from loguru import logger

from untanngle import camel_casing as cc
from untanngle import utils as ut


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
    begin_anchor: int = 0
    end_anchor: int = 0
    text_num: str = ""
    metadata: Dict[str, any] = field(default_factory=dict)


def as_class_name(string: str) -> str:
    return string[0].capitalize() + string[1:]


@dataclass
class AnnotationTransformer:
    project: str
    textrepo_url: str
    textrepo_versions: Dict[str, str]
    text_in_body: bool

    def as_web_annotation(self, ia: IAnnotation) -> Dict[str, Any]:
        body_type = f"{ia.namespace}:{as_class_name(ia.type)}"
        text_num = ia.text_num
        textrepo_version = self.textrepo_versions[text_num]
        anno = {
            "@context": [
                "http://www.w3.org/ns/anno.jsonld",
                {
                    "nlp": "https://ns.tt.di.huc.knaw.nl/nlp",
                    "pagexml": "https://ns.tt.di.huc.knaw.nl/pagexml",
                    "tf": "https://ns.tt.di.huc.knaw.nl/tf",
                    "tt": "https://ns.tt.di.huc.knaw.nl/tt",
                    "tei": "https://ns.tt.di.huc.knaw.nl/tei"
                }
            ],
            "type": "Annotation",
            "purpose": "tagging",
            "generated": datetime.today().isoformat(),
            "body": {
                "id": f"urn:{self.project}:{ia.type}:{ia.tf_node}",
                "type": body_type,
                "tf:textfabric_node": ia.tf_node
            },
            "target": [
                {
                    "source": f"{self.textrepo_url}/rest/versions/{textrepo_version}/contents",
                    "type": "Text",
                    "selector": {
                        "type": "tt:TextAnchorSelector",
                        "start": ia.begin_anchor,
                        "end": ia.end_anchor
                    }
                },
                {
                    "source": (
                        f"{self.textrepo_url}/view/versions/{textrepo_version}/segments/index/{ia.begin_anchor}/{ia.end_anchor}"),
                    "type": "Text"
                }
            ]
        }
        if self.text_in_body:
            anno["body"]["text"] = ia.text
        if ia.metadata:
            anno["body"]["metadata"] = {f"{k.replace('@', '_')}": v for k, v in ia.metadata.items()}
            if "type" not in anno["body"]["metadata"]:
                anno["body"]["metadata"]["type"] = f"tt:{as_class_name(ia.type)}Metadata"
        if ia.type == "letter":
            anno["body"]["metadata"]["folder"] = "proeftuin"
            anno["target"].append({
                "source": "https://images.diginfra.net/iiif/NL-HaNA_1.01.02%2F3783%2FNL-HaNA_1.01.02_3783_0002.jpg/full/full/0/default.jpg",
                "type": "Image"
            })
        if ia.type == "folder":
            anno["body"]["metadata"]["manifest"] = \
                "https://images.diginfra.net/api/pim/imageset/67533019-4ca0-4b08-b87e-fd5590e7a077/manifest"
            if "text" in anno["body"]:
                anno["body"].pop("text")
        else:
            canvas_target = {
                "@context": "https://knaw-huc.github.io/ns/huc-di-tt.jsonld",
                "source": "https://images.diginfra.net/api/pim/iiif/67533019-4ca0-4b08-b87e-fd5590e7a077/canvas/20633ef4-27af-4b13-9ffe-dfc0f9dad1d7",
                "type": "Canvas"
            }
            anno["target"].append(canvas_target)
        return anno


def convert(project: str,
            anno_files: List[str],
            text_files: List[str],
            textrepo_url: str,
            textrepo_file_versions: Dict[str, str],
            text_in_body: bool = False) -> List[Dict[str, Any]]:
    tf_tokens = read_tf_tokens(text_files)
    tf_annotations = []
    for anno_file in anno_files:
        tf_annotations.extend(read_tf_annotations(anno_file))
    return build_web_annotations(project=project,
                                 tf_annotations=tf_annotations,
                                 tokens_per_text=tf_tokens,
                                 textrepo_url=textrepo_url,
                                 textrepo_file_versions=textrepo_file_versions,
                                 text_in_body=text_in_body)


def read_tf_tokens(text_files):
    tokens_per_text = {}
    for text_file in text_files:
        text_num = get_file_num(text_file)
        logger.info(f"<= {text_file}")
        with open(text_file) as f:
            contents = json.load(f)
        tokens_per_text[text_num] = contents["_ordered_segments"]
    return tokens_per_text


def read_tf_annotations(anno_file):
    tf_annotations = []
    logger.info(f"<= {anno_file}")
    with open(anno_file) as f:
        content = json.load(f)
        for _id, properties in content.items():
            tf_annotations.append(
                TFAnnotation(id=_id, type=properties[0], namespace=properties[1],
                             body=properties[2], target=properties[3])
            )
    return tf_annotations


def modify_pb_annotations(ia: List[IAnnotation], tokens) -> List[IAnnotation]:
    pb_end_anchor = 0
    last_page_in_div = None
    for i, a in enumerate(ia):
        if is_div_with_pb(a):
            pb_end_anchor = a.end_anchor
            last_page_in_div = None
        elif a.type == "pb":
            if pb_end_anchor > a.begin_anchor:
                a.end_anchor = pb_end_anchor
            else:
                logger.warning(f"<pb> outside of <div>: {a}")
            if not last_page_in_div:
                last_page_in_div = i
            else:
                prev = ia[last_page_in_div]
                prev.end_anchor = a.begin_anchor - 1
                prev.text = text_of(prev, tokens)
            a.type = 'page'
            a.text = text_of(a, tokens)
    return ia


def text_of(a, tokens):
    return "".join(tokens[a.begin_anchor:a.end_anchor + 1])


def is_div_with_pb(a):
    return a.type == "div" \
        and "type" in a.metadata \
        and a.metadata["type"] in ("original", "translation", "postalData")


def sanity_check(ia: List[IAnnotation]):
    annotations_with_invalid_anchor_range = [a for a in ia if a.begin_anchor > a.end_anchor]
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
                ic(anno1.id, anno1.metadata, anno1.begin_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.begin_anchor, anno2.end_anchor)

    sentence_annotations = [a for a in ia if a.type == 'sentence']
    for i in range(len(sentence_annotations)):
        for j in range(i + 1, len(sentence_annotations)):
            anno1 = sentence_annotations[i]
            anno2 = sentence_annotations[j]
            if annotations_overlap(anno1, anno2):
                logger.error("Overlapping Sentence annotations: ")
                ic(anno1.id, anno1.metadata, anno1.begin_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.begin_anchor, anno2.end_anchor)

    note_annotations_without_lang = [a for a in ia if a.type == 'note' and 'lang' not in a.metadata]
    if note_annotations_without_lang:
        logger.error("There are note annotations without lang metadata:")
        ic(note_annotations_without_lang)


def annotations_overlap(anno1, anno2):
    return (anno1.text_num == anno2.text_num) and (anno1.end_anchor - 1) >= anno2.begin_anchor


def get_parent_lang(a: IAnnotation, node_parents: Dict[str, str], ia_idx: Dict[str, IAnnotation]) -> str:
    if a.id in node_parents:
        parent = ia_idx[node_parents[a.id]]
        if 'lang' in parent.metadata:
            return parent.metadata['lang']
        else:
            return get_parent_lang(parent, node_parents, ia_idx)
    else:
        # logger.warning(f"node {a.id} has no parents, and no metadata.lang -> returning default 'en'")
        return 'en'


def modify_note_annotations(ia: List[IAnnotation], node_parents: Dict[str, str]) -> List[IAnnotation]:
    ia_idx = {a.id: a for a in ia}
    for a in ia:
        if a.type == 'note' and 'lang' not in a.metadata:
            parent_lang = get_parent_lang(a, node_parents, ia_idx)
            a.metadata['lang'] = parent_lang
            # logger.info(f"enriched note: {a}")
    return ia


single_target_pattern = re.compile(r"(\d+):(\d+)")
range_target_pattern1 = re.compile(r"(\d+):(\d+)-(\d+)")
range_target_pattern2 = re.compile(r"(\d+):(\d+)-(\d+):(\d+)")


def build_web_annotations(project: str,
                          tf_annotations: List[TFAnnotation],
                          tokens_per_text: Dict[str, List[str]],
                          textrepo_url: str,
                          textrepo_file_versions: Dict[str, str],
                          text_in_body: bool):
    at = AnnotationTransformer(project=project,
                               textrepo_url=textrepo_url,
                               textrepo_versions=textrepo_file_versions,
                               text_in_body=text_in_body)
    ia_idx = {}
    note_target = {}
    node_parents = {}
    ref_links = []
    target_links = []
    for a in [a for a in tf_annotations]:
        match a.type:
            case 'element':
                match0 = single_target_pattern.fullmatch(a.target)
                match1 = range_target_pattern1.fullmatch(a.target)
                match2 = range_target_pattern2.fullmatch(a.target)
                if match2:
                    logger.warning(f"annotation spanning multiple texts: {a}")

                elif match1:
                    text_num = match1.group(1)
                    begin_anchor = int(match1.group(2))
                    end_anchor = int(match1.group(3))
                    text = "".join(tokens_per_text[text_num][begin_anchor:end_anchor])
                    ia = IAnnotation(id=a.id,
                                     namespace=a.namespace,
                                     type=a.body,
                                     text=text,
                                     text_num=text_num,
                                     begin_anchor=begin_anchor,
                                     end_anchor=end_anchor - 1)
                    ia_idx[a.id] = ia

                elif match0:
                    text_num = match0.group(1)
                    begin_anchor = end_anchor = int(match0.group(2))
                    text = "".join(tokens_per_text[text_num][begin_anchor:end_anchor])
                    ia = IAnnotation(id=a.id,
                                     namespace=a.namespace,
                                     type=a.body,
                                     text=text,
                                     text_num=text_num,
                                     begin_anchor=begin_anchor,
                                     end_anchor=end_anchor)
                    ia_idx[a.id] = ia

                else:
                    logger.warning(f"unknown element target pattern: {a}")
            case 'node':
                anno_id = a.target
                if anno_id in ia_idx:
                    ia_idx[anno_id].tf_node = int(a.body)
                # else:
                #     logger.warning(f"node target ({anno_id}) not in ia_idx index")
                #     ic(a)
            case 'mark':
                note_anno_id = a.target
                if note_anno_id in ia_idx:
                    element_anno_id = int(a.body)
                    note_target[note_anno_id] = element_anno_id
                else:
                    logger.warning(f"mark target ({note_anno_id}) not in ia_idx index")
                    ic(a)
            case 'attribute':
                element_anno_id = a.target
                if element_anno_id in ia_idx:
                    (k, v) = a.body.split('=', 1)
                    if k == 'id':
                        k = 'tei:id'
                    ia_idx[element_anno_id].metadata[k] = v
                # else:
                #     logger.warning(f"attribute target ({element_anno_id}) not in ia_idx index")
                #     ic(a)
            case 'anno':
                element_anno_id = a.target
                if element_anno_id in ia_idx:
                    ia_idx[element_anno_id].metadata["anno"] = a.body
                else:
                    logger.warning(f"anno target ({element_anno_id}) not in ia_idx index")
                    ic(a)
            case 'format':
                # logger.warning("format annotation skipped")
                # ic(a)
                pass
            case 'pi':
                logger.warning("pi annotation skipped")
                ic(a)
                pass
            case 'edge':
                match a.body:
                    case 'parent':
                        child_id, parent_id = a.target.split('->')
                        node_parents[child_id] = parent_id
                    case 'link_ref':
                        from_id, to_id = a.target.split('->')
                        ref_links.append((from_id, to_id))
                        pass
                    case 'link_target':
                        from_id, to_id = a.target.split('->')
                        target_links.append((from_id, to_id))
                        pass
                    case _:
                        if a.body.startswith('sibling='):
                            logger.warning("edge/sibling annotation skipped")
                            pass
                        else:
                            logger.warning(f"unhandled edge body: {a.body}")

            case _:
                logger.warning(f"unhandled type: {a.type}")

    ia = sorted(ia_idx.values(),
                key=lambda anno: (anno.begin_anchor * 100_000 + (1000 - anno.end_anchor)) * 100_000 + anno.tf_node)

    # ia = modify_pb_annotations(ia, tokens)
    # ic(node_parents)
    ia = modify_note_annotations(ia, node_parents)

    # TODO: convert ptr annotations to annotation linking the ptr target to the body.id of the m:Note with the corresponding id
    # TODO: convert rs annotations to annotation linking the rkd url in metadata.anno to the rd target
    # TODO: convert ref annotations

    sanity_check(ia)

    tf_node_to_ia_id = {a.tf_node: a.id for a in ia}
    web_annotations = [at.as_web_annotation(a) for a in ia]
    ia_id_to_body_id = {tf_node_to_ia_id[wa["body"]["tf:textfabric_node"]]: wa["body"]["id"] for wa in web_annotations}

    ref_annotations = [
        as_link_anno(from_ia_id, to_ia_id, "referencing", ia_id_to_body_id)
        for from_ia_id, to_ia_id in ref_links
    ]
    web_annotations.extend(ref_annotations)

    target_annotations = [
        as_link_anno(from_ia_id, to_ia_id, "targeting", ia_id_to_body_id)
        for from_ia_id, to_ia_id in target_links
    ]
    web_annotations.extend(target_annotations)
    return [cc.keys_to_camel_case(a) for a in web_annotations]


def as_link_anno(from_ia_id: str, to_ia_id: str, purpose: str, ia_id_to_body_id: Dict[str, str]) -> Dict[str, str]:
    body_id = ia_id_to_body_id[from_ia_id]
    target_id = ia_id_to_body_id[to_ia_id]
    return {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "type": "Annotation",
        "purpose": purpose,
        "generated": datetime.today().isoformat(),
        "body": body_id,
        "target": target_id
    }


file_num_pattern = re.compile(r".*-(\d+).json")


def get_file_num(tf_text_file: str) -> str:
    match = file_num_pattern.match(tf_text_file)
    if match:
        return match.group(1)


def untangle_tf_export(
        project_name: str,
        text_files: List[str],
        anno_files: List[str],
        textrepo_base_uri: str,
        export_path: str,
        excluded_types: List[str] = []
):
    start = time.perf_counter()
    textrepo_file_version = ut.upload_to_tr(textrepo_base_uri=textrepo_base_uri,
                                            project_name=project_name,
                                            tf_text_files=text_files)
    web_annotations = convert(project=project_name,
                              anno_files=anno_files,
                              text_files=text_files,
                              textrepo_url=textrepo_base_uri,
                              textrepo_file_versions=textrepo_file_version)
    logger.info(f"{len(web_annotations)} annotations")
    filtered_web_annotations = [a for a in web_annotations if
                                'type' in a['body'] and a['body']['type'] not in excluded_types]
    ut.store_web_annotations(web_annotations=filtered_web_annotations, export_path=export_path)
    print(f"text files: {len(text_files)}")
    ut.show_annotation_counts(web_annotations, excluded_types)
    end = time.perf_counter()
    print(f"untangling {project_name} took {end - start:0.4f} seconds")
