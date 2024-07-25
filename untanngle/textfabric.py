import csv
import glob
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Union

from icecream import ic
from loguru import logger

from untanngle import camel_casing as cc
from untanngle import utils as ut


@dataclass
class TFUntangleConfig:
    project_name: str
    data_path: str
    export_path: str
    tier0_type: str
    excluded_types: list[str]
    textrepo_base_uri: Union[str, None] = None
    text_in_body: bool = False


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
    metadata: dict[str, any] = field(default_factory=dict)


@dataclass
class AnnotationTransformer:
    project: str
    textrepo_url: str
    textrepo_versions: dict[str, str]
    text_in_body: bool

    def as_web_annotation(self, ia: IAnnotation) -> dict[str, Any]:
        body_type = f"{ia.namespace}:{as_class_name(ia.type)}"
        text_num = ia.text_num
        textrepo_version = self.textrepo_versions[text_num]
        body_id = f"urn:{self.project}:{ia.type}:{ia.tf_node}"
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
            "id": f"urn:{self.project}:annotation:{ia.id}",
            "purpose": "tagging",
            "generated": datetime.today().isoformat(),
            "body": {
                "id": body_id,
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
            metadata = {}
            if "type" not in ia.metadata:
                metadata["type"] = f"tt:{as_class_name(ia.type)}Metadata"
            metadata.update({
                f"{k.replace('@', '_').replace('manifestUrl', 'manifest')}": fix_urls(v)
                for k, v in ia.metadata.items()
            })
            # if 'manifest' in metadata:
            #     metadata['manifest'] = metadata['manifest'].replace('suriano.huygens.knaw.nl/manifests',
            #                                                         'suriano.diginfra.org/manif')
            if "prev" in ia.metadata:
                prevNode = ia.metadata["prev"]
                metadata.pop("prev")
                metadata[f"prev{ia.type.capitalize()}"] = f"urn:{self.project}:{ia.type}:{prevNode}"
                nextNode = ia.metadata["next"]
                metadata.pop("next")
                metadata[f"next{ia.type.capitalize()}"] = f"urn:{self.project}:{ia.type}:{nextNode}"
            anno["body"]["metadata"] = metadata
        # if ia.type == "letter":
        #     # anno["body"]["metadata"]["folder"] = "proeftuin"
        #     anno["target"].append({
        #         "source": "https://images.diginfra.net/iiif/NL-HaNA_1.01.02%2F3783%2FNL-HaNA_1.01.02_3783_0002.jpg/full/max/0/default.jpg",
        #         "type": "Image"
        #     })
        if 'canvasUrl' in ia.metadata:
            canvas_target = {
                "@context": "https://knaw-huc.github.io/ns/huc-di-tt.jsonld",
                "source": fix_urls(ia.metadata['canvasUrl']),
                "type": "Canvas"
            }
            anno['body']['metadata'].pop('canvasUrl')
            anno["target"].append(canvas_target)
        return anno


def fix_urls(value: str) -> str:
    return value.replace('suriano.huygens.knaw.nl/manifests', 'suriano.diginfra.org/manif').replace(
        'suriano.huygens.knaw.nl', 'suriano.diginfra.org')


def untangle_tf_export(config: TFUntangleConfig):
    start = time.perf_counter()
    text_files = sorted(glob.glob(f'{config.data_path}/text-*.tsv'))
    anno_files = sorted(glob.glob(f"{config.data_path}/anno-*.tsv"))
    anno2node_path = f"{config.data_path}/anno2node.tsv"
    export_dir = f"{config.export_path}/{config.project_name}"
    os.makedirs(name=export_dir, exist_ok=True)

    out_files = []
    for tsv in text_files:
        text_num = get_file_num(tsv)
        json_path = f"{export_dir}/textfile-{text_num}.json"
        segments = read_tokens(tsv)
        store_segmented_text(segments=segments, store_path=json_path)
        out_files.append(json_path)

    if config.textrepo_base_uri:
        textrepo_file_version = ut.upload_to_tr(textrepo_base_uri=config.textrepo_base_uri,
                                                project_name=config.project_name,
                                                tf_text_files=out_files)
    else:
        textrepo_file_version = dummy_version(text_files)
    web_annotations = convert(project=config.project_name, anno_files=anno_files, text_files=text_files,
                              anno2node_path=anno2node_path, text_in_body=config.text_in_body,
                              textrepo_url=config.textrepo_base_uri, textrepo_file_versions=textrepo_file_version)
    logger.info(f"{len(web_annotations)} annotations")
    sanity_check1(web_annotations, config.tier0_type)
    filtered_web_annotations = [
        a for a in web_annotations if
        ('type' in a['body'] and a['body']['type'] not in config.excluded_types)
        or 'type' not in a['body']
    ]
    ut.store_web_annotations(web_annotations=filtered_web_annotations, export_path=f"{export_dir}/web-annotations.json")
    end = time.perf_counter()
    print_report(config, text_files, web_annotations, filtered_web_annotations, start, end)


def print_report(config, text_files, web_annotations, filtered_web_annotations, start, end):
    print(f"untangling {config.project_name} took {end - start:0.4f} seconds")
    print(f"text files: {len(text_files)}")
    print(f"annotations: {len(filtered_web_annotations)}")
    print(f"tier0 = {config.tier0_type}")
    ut.show_annotation_counts(web_annotations, config.excluded_types)


def as_class_name(string: str) -> str:
    return string[0].capitalize() + string[1:]


def convert(project: str, anno_files: list[str], text_files: list[str], anno2node_path: str, textrepo_url: str,
            textrepo_file_versions: dict[str, str], text_in_body: bool = False) -> list[dict[str, Any]]:
    tf_tokens = read_tf_tokens(text_files)
    tf_annotations = []
    for anno_file in anno_files:
        tf_annotations.extend(read_tf_annotations(anno_file))
    return build_web_annotations(project=project,
                                 tf_annotations=tf_annotations,
                                 tokens_per_text=tf_tokens,
                                 textrepo_url=textrepo_url,
                                 textrepo_file_versions=textrepo_file_versions,
                                 text_in_body=text_in_body,
                                 anno2node_path=anno2node_path)


def read_tf_tokens(text_files) -> dict[str, list[str]]:
    tokens_per_text = {}
    for text_file in text_files:
        text_num = get_file_num(text_file)
        tokens = read_tokens(text_file)
        tokens_per_text[text_num] = tokens
    return tokens_per_text


def read_tf_tokens_from_json(text_files):
    tokens_per_text = {}
    for text_file in text_files:
        text_num = get_file_num(text_file)
        logger.info(f"<= {text_file}")
        with open(text_file) as f:
            contents = json.load(f)
        tokens_per_text[text_num] = contents["_ordered_segments"]
    return tokens_per_text


def read_tf_annotations(anno_file) -> list[TFAnnotation]:
    return [
        TFAnnotation(
            id=row["annoid"],
            type=row["kind"],
            namespace=row["namespace"],
            body=row["body"],
            target=row["target"]
        )
        for row in read_tsv_records(anno_file)
    ]


def read_tf_annotations_from_json(anno_file):
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


def read_tsv_records(path: str) -> list[dict[str, any]]:
    # csv.field_size_limit(sys.maxsize)
    logger.info(f"<= {path}")
    with open(path, encoding='utf8') as f:
        records = [row for row in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)]
    return records  # type *is* correct!


def token(row: list[str]) -> str:
    if row:
        return row[0].replace('\\n', '\n').replace('\\t', '\t')
    else:
        return ""


def read_tokens(path: str) -> list[str]:
    logger.info(f"<= {path}")
    with open(path, encoding='utf8') as f:
        tokens = [token(row) for row in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)]
    return tokens[1:]  # type *is* correct!


def modify_pb_annotations(ia: list[IAnnotation], tokens: list[str]) -> list[IAnnotation]:
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


def sanity_check(ia: list[IAnnotation]):
    logger.info("check for annotations_with_invalid_anchor_range")
    annotations_with_invalid_anchor_range = [a for a in ia if a.begin_anchor > a.end_anchor]
    if annotations_with_invalid_anchor_range:
        logger.error("There are annotations with invalid anchor range:")
        ic(annotations_with_invalid_anchor_range)

    logger.info("check for overlapping letter annotations")
    letter_annotations = [a for a in ia if a.type == 'letter']
    for i in range(len(letter_annotations)):
        for j in range(i + 1, len(letter_annotations)):
            anno1 = letter_annotations[i]
            anno2 = letter_annotations[j]
            if annotations_overlap(anno1, anno2):
                logger.error("Overlapping Letter annotations: ")
                ic(anno1.id, anno1.metadata, anno1.begin_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.begin_anchor, anno2.end_anchor)

    logger.info("check for overlapping sentence annotations")
    sentence_annotations = [a for a in ia if a.type == 'sentence']
    for i in range(len(sentence_annotations)):
        for j in range(i + 1, len(sentence_annotations)):
            anno1 = sentence_annotations[i]
            anno2 = sentence_annotations[j]
            if annotations_overlap(anno1, anno2):
                logger.error("Overlapping Sentence annotations: ")
                ic(anno1.id, anno1.metadata, anno1.begin_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.begin_anchor, anno2.end_anchor)

    logger.info("check for note annotations without lang")
    note_annotations_without_lang = [a for a in ia if a.type == 'note' and 'lang' not in a.metadata]
    if note_annotations_without_lang:
        logger.error("There are note annotations without lang metadata:")
        ic(note_annotations_without_lang)


def annotations_overlap(anno1, anno2):
    return (anno1.text_num == anno2.text_num) and (anno1.end_anchor - 1) >= anno2.begin_anchor


def get_parent_lang(a: IAnnotation, node_parents: dict[str, str], ia_idx: dict[str, IAnnotation]) -> str:
    if a.id in node_parents:
        parent = ia_idx[node_parents[a.id]]
        if 'lang' in parent.metadata:
            return parent.metadata['lang']
        else:
            return get_parent_lang(parent, node_parents, ia_idx)
    else:
        # logger.warning(f"node {a.id} has no parents, and no metadata.lang -> returning default 'en'")
        return 'en'


def modify_note_annotations(ia: list[IAnnotation], node_parents: dict[str, str]) -> list[IAnnotation]:
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


def build_web_annotations(
        project: str,
        tf_annotations: list[TFAnnotation],
        tokens_per_text: dict[str, list[str]],
        textrepo_url: str,
        textrepo_file_versions: dict[str, str],
        text_in_body: bool,
        anno2node_path: str
) -> list[dict]:
    at = AnnotationTransformer(project=project,
                               textrepo_url=textrepo_url,
                               textrepo_versions=textrepo_file_versions,
                               text_in_body=text_in_body)
    tf_node_for_annotation_id = {row['annotation']: row['node'] for row in read_tsv_records(anno2node_path)}
    tf_annotation_idx = {}
    note_target = {}
    node_parents = {}
    ref_links = []
    target_links = []
    bar = ut.default_progress_bar(len(tf_annotations))
    for i, tf_annotation in enumerate(tf_annotations):
        bar.update(i)
        match tf_annotation.type:
            case 'element':
                handle_element(tf_annotation, tf_annotation_idx, tokens_per_text)
            # case 'node':
            #     anno_id = a.target
            #     if anno_id in tf_annotation_idx:
            #         tf_annotation_idx[anno_id].tf_node = int(a.body)
            #     # else:
            #     #     logger.warning(f"node target ({anno_id}) not in tf_annotation_idx index")
            #     #     ic(a)
            case 'mark':
                handle_mark(tf_annotation, note_target, tf_annotation_idx)
            case 'attribute':
                handle_attribute(tf_annotation, tf_annotation_idx)
            case 'anno':
                handle_anno(tf_annotation, tf_annotation_idx)
            case 'format':
                handle_format()
            case 'pi':
                handle_pi(tf_annotation)
            case 'edge':
                handle_edge(tf_annotation, node_parents, ref_links, target_links)

            case _:
                logger.warning(f"unhandled type: {tf_annotation.type}")
    print()
    tf_annos = sorted(tf_annotation_idx.values(),
                      key=lambda anno: (anno.begin_anchor * 100_000 + (
                              1000 - anno.end_anchor)) * 100_000 + anno.tf_node)

    for tfa in tf_annos:
        tfa.tf_node = tf_node_for_annotation_id[tfa.id]

    # tf_annos = modify_pb_annotations(tf_annos, tokens)
    # ic(node_parents)
    logger.info("modify_note_annotations")
    tf_annos = modify_note_annotations(tf_annos, node_parents)

    # TODO: convert ptr annotations to annotation linking the ptr target to the body.id of the m:Note with the corresponding id
    # TODO: convert rs annotations to annotation linking the rkd url in metadata.anno to the rd target
    # TODO: convert ref annotations

    logger.info("sanity_check")
    sanity_check(tf_annos)

    logger.info("as_web_annotation")
    tf_node_to_ia_id = {a.tf_node: a.id for a in tf_annos}
    web_annotations = [at.as_web_annotation(a) for a in tf_annos]
    tf_id_to_body_id = {tf_node_to_ia_id[wa["body"]["tf:textfabric_node"]]: wa["body"]["id"] for wa in web_annotations}

    # ic(ref_links)
    logger.info("ref_annotations")
    ref_annotations = [
        as_link_anno(from_ia_id, to_ia_id, "referencing", tf_id_to_body_id, project)
        for from_ia_id, to_ia_id in ref_links
    ]
    web_annotations.extend(ref_annotations)

    # ic(target_links)
    logger.info("target_annotations")
    target_annotations = [
        as_link_anno(from_ia_id, to_ia_id, "targeting", tf_id_to_body_id, project)
        for from_ia_id, to_ia_id in target_links
    ]
    web_annotations.extend(target_annotations)

    logger.info("keys_to_camel_case")
    return [cc.keys_to_camel_case(a) for a in web_annotations]


def handle_format():
    # logger.warning("format annotation skipped")
    # ic(a)
    pass


def handle_edge(tf_annotation, node_parents, ref_links, target_links):
    match tf_annotation.body:
        case 'parent':
            child_id, parent_id = tf_annotation.target.split('->')
            node_parents[child_id] = parent_id
        case 'link_ref':
            from_id, to_id = tf_annotation.target.split('->')
            ref_links.append((from_id, to_id))
            pass
        case 'link_target':
            from_id, to_id = tf_annotation.target.split('->')
            target_links.append((from_id, to_id))
            pass
        case _:
            if tf_annotation.body.startswith('sibling='):
                # logger.warning("edge/sibling annotation skipped")
                pass
            else:
                logger.warning(f"unhandled edge body: {tf_annotation.body}")


def handle_pi(tf_annotation):
    logger.warning("pi annotation skipped")
    ic(tf_annotation)
    pass


def handle_anno(tf_annotation, tf_annotation_idx):
    element_anno_id = tf_annotation.target
    if element_anno_id in tf_annotation_idx:
        tf_annotation_idx[element_anno_id].metadata["anno"] = tf_annotation.body
    else:
        logger.warning(f"anno target ({element_anno_id}) not in tf_annotation_idx index")
        ic(tf_annotation)


def handle_attribute(tf_annotation, tf_annotation_idx):
    element_anno_id = tf_annotation.target
    if element_anno_id in tf_annotation_idx:
        (k, v) = tf_annotation.body.split('=', 1)
        if k == 'id':
            k = 'tei:id'
        tf_annotation_idx[element_anno_id].metadata[k] = v
    # else:
    #     logger.warning(f"attribute target ({element_anno_id}) not in tf_annotation_idx index")
    #     ic(a)


def handle_mark(tf_annotation, note_target, tf_annotation_idx):
    note_anno_id = tf_annotation.target
    if note_anno_id in tf_annotation_idx:
        element_anno_id = int(tf_annotation.body)
        note_target[note_anno_id] = element_anno_id
    else:
        logger.warning(f"mark target ({note_anno_id}) not in tf_annotation_idx index")
        ic(tf_annotation)


def handle_element(a, tf_annotation_idx, tokens_per_text):
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
        tf_annos = IAnnotation(id=a.id,
                               namespace=a.namespace,
                               type=a.body,
                               text=text,
                               text_num=text_num,
                               begin_anchor=begin_anchor,
                               end_anchor=end_anchor - 1)
        tf_annotation_idx[a.id] = tf_annos

    elif match0:
        text_num = match0.group(1)
        begin_anchor = end_anchor = int(match0.group(2))
        text = "".join(tokens_per_text[text_num][begin_anchor:end_anchor])
        tf_annos = IAnnotation(id=a.id,
                               namespace=a.namespace,
                               type=a.body,
                               text=text,
                               text_num=text_num,
                               begin_anchor=begin_anchor,
                               end_anchor=end_anchor)
        tf_annotation_idx[a.id] = tf_annos

    else:
        logger.warning(f"unknown element target pattern: {a}")


def as_link_anno(
        from_ia_id: str,
        to_ia_id: str,
        purpose: str,
        ia_id_to_body_id: dict[str, str],
        project_name: str
) -> dict[str, str]:
    body_id = ia_id_to_body_id[from_ia_id]
    target_id = ia_id_to_body_id[to_ia_id]
    return {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "id": f"urn:{project_name}:annotation:{uuid.uuid4()}",
        "type": "Annotation",
        "purpose": purpose,
        "generated": datetime.today().isoformat(),
        "body": body_id,
        "target": target_id
    }


file_num_pattern_from_json = re.compile(r".*-(\d+).json")
file_num_pattern = re.compile(r".*-(\d+).tsv")


def get_file_num(tf_text_file: str) -> str:
    match = file_num_pattern.match(tf_text_file)
    if match:
        return match.group(1)
    else:
        match = file_num_pattern_from_json.match(tf_text_file)
        if match:
            return match.group(1)


def sanity_check1(web_annotations: list, tier0_type: str):
    tier0_annotations = [a for a in web_annotations if "type" in a['body'] and a['body']['type'] == tier0_type]
    if not tier0_annotations:
        logger.error(f"no tier0 annotations found, tier0 = '{tier0_type}'")
    else:
        for a in tier0_annotations:
            if 'manifest' not in a['body']['metadata']:
                logger.error(f"missing required body.metadata.manifest field for {a}")


def store_segmented_text(segments: list[str], store_path: str):
    data = {"_ordered_segments": segments}
    logger.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='UTF8') as filehandle:
        json.dump(data, filehandle, indent=4, ensure_ascii=False)


def dummy_version(text_files):
    textrepo_file_version = {}
    for text_file in text_files:
        file_num = get_file_num(text_file)
        textrepo_file_version[file_num] = f"placeholder-{file_num}"
    return textrepo_file_version
