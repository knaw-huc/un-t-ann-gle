import copy
import csv
import glob
import json
import os
import re
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable

from icecream import ic
from intervaltree import IntervalTree
from loguru import logger

from untanngle import camel_casing as cc
from untanngle import utils as ut
from untanngle.annotations import simple_image_target, image_target

range_target_pattern1 = re.compile(r"(\d+):(\d+)-(\d+)")
range_target_pattern2 = re.compile(r"(\d+):(\d+)-(\d+):(\d+)")
single_target_pattern = re.compile(r"(\d+):(\d+)")

paragraph_types = {
    "author",
    "biblScope",
    "collection",
    "date",
    "editor",
    "head",
    "idno",
    "institution",
    "name",
    # "note",
    "num",
    "p",
    "person",
    "resp",
    "settlement",
    "title",
    "l",
    # "lg",
}


@dataclass
class TFUntangleConfig:
    project_name: str
    data_path: str
    export_path: str
    tier0_type: str
    excluded_types: list[str]
    textrepo_base_uri_internal: Optional[str] = None
    textrepo_base_uri_external: Optional[str] = None
    text_in_body: bool = False
    with_facsimiles: bool = True
    show_progress: bool = False
    log_file_path: Optional[str] = None
    editem_project: bool = False
    apparatus_data_directory: Optional[str] = None
    graphic_url_mapper: Optional[Callable[[str], str]] = None


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextCoords:
    begin_anchor: int
    begin_char_offset: int
    end_anchor: int
    end_char_offset: int


@dataclass
class AnnotationTransformer:
    project: str
    textrepo_url: str
    textrepo_versions: dict[str, dict[str, str]]
    text_in_body: bool
    logical_coords_for_physical_anchor_per_text: dict[str, dict[str, TextCoords]]
    entity_metadata: dict[str, dict[str, str]]
    entity_for_ref: dict[str, dict[str, Any]] = field(default_factory=dict)
    letter_id_for_tf_node: dict[int, str] = field(default_factory=dict)
    graphic_url_mapper: Callable[[str], str] = staticmethod(lambda s: s)

    errors = set()

    def as_web_annotation(self, ia: IAnnotation) -> dict[str, Any]:
        body_type = f"{ia.namespace}:{_as_class_name(ia.type)}"
        text_num = ia.text_num
        textrepo_physical_version = self.textrepo_versions[text_num]['physical']
        textrepo_logical_version = self.textrepo_versions[text_num]['logical']
        if ia.type == "letter":
            body_id = f"urn:{self.project}:{ia.type}:{ia.metadata["file"]}"
        elif ia.type == "file" and ia.metadata["file"] == "introduction":
            body_id = f"urn:{self.project}:{ia.type}:intro"
        else:
            body_id = f"urn:{self.project}:{ia.type}:{ia.tf_node}"

        logical_text_coords = self._calculate_logical_text_coords(ia)
        anno = {
            "@context": [
                "http://www.w3.org/ns/anno.jsonld",
                {
                    "nlp": "https://humanities.knaw.nl/def/nlp/",
                    "pagexml": "https://humanities.knaw.nl/def/pagexml/",
                    "tf": "https://humanities.knaw.nl/def/text-fabric/",
                    "tt": "https://humanities.knaw.nl/def/team-text/",
                    "tei": "http://www.tei-c.org/ns/1.0#"
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
                    "source": f"{self.textrepo_url}/rest/versions/{textrepo_physical_version}/contents",
                    "type": "Text",
                    "selector": {
                        "type": "tt:TextAnchorSelector",
                        "start": ia.begin_anchor,
                        "end": ia.end_anchor
                    }
                },
                {
                    "source": f"{self.textrepo_url}/view/versions/{textrepo_physical_version}/segments/index/"
                              f"{ia.begin_anchor}/{ia.end_anchor}",
                    "type": "Text"
                }
            ]
        }
        if logical_text_coords.end_char_offset > -1:
            anno["target"].extend([
                {
                    "source": f"{self.textrepo_url}/rest/versions/{textrepo_logical_version}/contents",
                    "type": "LogicalText",
                    "selector": {
                        "type": "tt:TextAnchorSelector",
                        "start": logical_text_coords.begin_anchor,
                        "end": logical_text_coords.end_anchor,
                        "beginCharOffset": logical_text_coords.begin_char_offset,
                        "endCharOffset": logical_text_coords.end_char_offset
                    }
                },
                {
                    "source": f"{self.textrepo_url}/view/versions/{textrepo_logical_version}/segments/index/"
                              f"{logical_text_coords.begin_anchor}/{logical_text_coords.begin_char_offset}/"
                              f"{logical_text_coords.end_anchor}/{logical_text_coords.end_char_offset}",
                    "type": "LogicalText"
                }

            ])
        else:
            anno["target"].extend([
                {
                    "source": f"{self.textrepo_url}/rest/versions/{textrepo_logical_version}/contents",
                    "type": "LogicalText",
                    "selector": {
                        "type": "tt:TextAnchorSelector",
                        "start": logical_text_coords.begin_anchor,
                        "end": logical_text_coords.end_anchor
                    }
                },
                {
                    "source": f"{self.textrepo_url}/view/versions/{textrepo_logical_version}/segments/index/"
                              f"{logical_text_coords.begin_anchor}/{logical_text_coords.end_anchor}",
                    "type": "LogicalText"
                }

            ])

        if self.text_in_body:
            anno["body"]["text"] = ia.text
        if ia.metadata:
            metadata: dict[str, Any] = {
                "type": f"tt:{_as_class_name(ia.type)}Metadata"
            }

            metadata.update(
                (self._normalized_metadata_field_name(k), self._normalized_metadata_value(v))
                for k, v in ia.metadata.items()
            )

            if "prev" in ia.metadata:
                prev_node = ia.metadata["prev"]
                metadata.pop("prev")
                if prev_node in self.letter_id_for_tf_node:
                    prev_node = self.letter_id_for_tf_node[prev_node]
                metadata[f"prev{ia.type.capitalize()}"] = f"urn:{self.project}:{ia.type}:{prev_node}"

            if "next" in ia.metadata:
                next_node = ia.metadata["next"]
                metadata.pop("next")
                if next_node in self.letter_id_for_tf_node:
                    next_node = self.letter_id_for_tf_node[next_node]
                metadata[f"next{ia.type.capitalize()}"] = f"urn:{self.project}:{ia.type}:{next_node}"

            if "eid" in ia.metadata:
                entity_id = f"{ia.metadata['eid']}-{ia.metadata['kind']}"
                metadata["entityId"] = f"urn:{self.project}:entity:{entity_id}"
                if self.entity_metadata:
                    metadata["details"] = [
                        {"label": mk, "value": mv}
                        for mk, mv
                        in self.entity_metadata[entity_id].items()
                    ]

            # if "url" in ia.metadata:
            #     ic(ia)
            #     ic(self.graphic_url_mapper)

            if "url" in ia.metadata and ia.type == "graphic" and self.graphic_url_mapper:
                metadata["url"] = self.graphic_url_mapper(ia.metadata["url"])

            anno["body"]["metadata"] = metadata

            if 'canvasUrl' in ia.metadata:
                canvas_target = {
                    "@context": "https://knaw-huc.github.io/ns/huc-di-tt.jsonld",
                    "source": ia.metadata['canvasUrl'],
                    "type": "Canvas"
                }
                if 'xywh' in ia.metadata:
                    canvas_target["selector"] = [{
                        "@context": "http://iiif.io/api/annex/openannotation/context.json",
                        "type": "iiif:ImageApiSelector",
                        "region": ia.metadata['xywh']
                    }]
                anno['body']['metadata'].pop('canvasUrl')
                anno["target"].append(canvas_target)
        return anno

    def create_entity_annotations(self) -> list[dict[str, Any]]:
        return [
            self._entity_metadata_annotation(k, v)
            for k, v in self.entity_metadata.items()
        ]

    def _calculate_logical_text_coords(self, ia: IAnnotation) -> TextCoords:
        if ia.begin_anchor not in self.logical_coords_for_physical_anchor_per_text[ia.text_num]:
            ic(self.logical_coords_for_physical_anchor_per_text[ia.text_num])
            ic(ia)
        logical_start_coords = self.logical_coords_for_physical_anchor_per_text[ia.text_num][ia.begin_anchor]
        # last_key = len(self.logical_coords_for_physical_anchor_per_text[ia.text_num].keys())
        if ia.end_anchor in self.logical_coords_for_physical_anchor_per_text[ia.text_num]:
            logical_end_coords = self.logical_coords_for_physical_anchor_per_text[ia.text_num][ia.end_anchor]
        else:
            # TODO: this should never happen!!!
            mydict = self.logical_coords_for_physical_anchor_per_text[ia.text_num]
            last_key = sorted([k for k in mydict.keys()])[-1]
            logical_end_coords = self.logical_coords_for_physical_anchor_per_text[ia.text_num][last_key]

        return TextCoords(
            begin_anchor=logical_start_coords.begin_anchor,
            begin_char_offset=logical_start_coords.begin_char_offset,
            end_anchor=logical_end_coords.end_anchor,
            end_char_offset=logical_end_coords.end_char_offset
        )

    def _entity_metadata_annotation(self, key: str, value: dict[str, str]) -> dict[str, Any]:
        body_id = f"urn:{self.project}:entity_metadata:{key}"
        entity_id = f"urn:{self.project}:entity:{key}"
        return {
            "@context": [
                "http://www.w3.org/ns/anno.jsonld"
            ],
            "type": "Annotation",
            "id": f"urn:{self.project}:annotation:{key}",
            "generated": datetime.today().isoformat(),
            "body": {
                "id": body_id,
                "type": "EntityMetadata",
                "metadata": [{"label": mk, "value": mv} for mk, mv in value.items()]
            },
            "target": entity_id
        }

    @staticmethod
    def _normalized_metadata_field_name(field_name: str) -> str:
        return field_name.replace('@', '_').replace('manifestUrl', 'manifest').replace('type', 'tei:type')

    def _normalized_metadata_value(self, value: str) -> list[dict[str, Any]] | str:
        if ".xml#" in value:
            return [self._ref_to_entity(v) for v in value.split(" ")]
        else:
            return value

    def _ref_to_entity(self, ref: str) -> dict[str, Any]:
        key = ref.replace('.xml#', '/')
        if key in self.entity_for_ref:
            return self.entity_for_ref[key]
        else:
            self.errors.add(f"no entity found for reference {ref}")
            return {ref: None}


def _map_tf_node_to_letter_id(tf_annos: list[IAnnotation]) -> dict[int, str]:
    letter_annos = [a for a in tf_annos if a.type == "letter"]
    return {a.tf_node: a.metadata["file"] for a in letter_annos}


def untangle_tf_export(config: TFUntangleConfig) -> list[str]:
    errors = []
    start = time.perf_counter()
    text_files = sorted(glob.glob(f'{config.data_path}/text-*.tsv'))
    anno_files = sorted(glob.glob(f"{config.data_path}/anno-*.tsv"))
    anno2node_path = f"{config.data_path}/anno2node.tsv"
    entity_meta_path = f"{config.data_path}/entitymeta.json"
    logical_pairs_path = f"{config.data_path}/logicalpairs.tsv"
    pos_to_node_path = f"{config.data_path}/pos2node.tsv"
    export_dir = f"{config.export_path}/{config.project_name}"
    os.makedirs(name=export_dir, exist_ok=True)

    if not config.show_progress:
        logger.remove()
        logger.add(sys.stdout, level="WARNING")

    if config.log_file_path:
        logger.remove()
        if os.path.exists(config.log_file_path):
            os.remove(config.log_file_path)
        logger.add(config.log_file_path)

    entity_metadata = _load_entity_metadata(entity_meta_path)
    entity_for_ref, load_entities_errors = _load_entities(f"{config.apparatus_data_directory}")
    errors.extend(load_entities_errors)
    node_for_pos = _load_node_for_pos(pos_to_node_path)
    # ic(node_for_pos)
    token_subst = _read_token_substitutions(logical_pairs_path)
    # ic(token_subst)

    tokens_per_file = _read_tf_tokens(text_files)

    raw_tf_annotations = []
    for anno_file in anno_files:
        raw_tf_annotations.extend(_read_raw_tf_annotations(anno_file))
    ref_links, target_links, tf_annos = _merge_raw_tf_annotations(raw_tf_annotations, anno2node_path, tokens_per_file,
                                                                  config.show_progress)

    letter_id_for_tf_node = _map_tf_node_to_letter_id(tf_annos)
    out_files = []
    text_nums = []
    for tsv in text_files:
        text_num = ut.get_file_num(tsv)
        text_nums += text_num
        json_path = f"{export_dir}/textfile-physical-{text_num}.json"
        segments = _read_tokens(tsv)
        _store_segmented_text(segments=segments, store_path=json_path)
        out_files.append(json_path)

    paragraph_ranges = _determine_paragraphs(tf_annos, tokens_per_file)
    # debug_paragraphs(paragraph_ranges, tokens_per_text)

    logical_file_paths, logical_coords_for_physical_anchor_per_text = _store_logical_text_files(
        export_dir,
        paragraph_ranges,
        tokens_per_file,
        node_for_pos,
        token_subst
    )
    out_files.extend(logical_file_paths)

    if config.textrepo_base_uri_internal:
        textrepo_file_versions = ut.upload_to_tr(textrepo_base_uri=config.textrepo_base_uri_internal,
                                                 project_name=config.project_name,
                                                 tf_text_files=out_files)
    else:
        textrepo_file_versions = _dummy_version(text_files)

    textrepo_external_url = config.textrepo_base_uri_external if config.textrepo_base_uri_external else config.textrepo_base_uri_internal
    assert textrepo_external_url is not None
    web_annotations, conversion_errors = _tf_annotations_to_web_annotations(
        tf_annos=tf_annos,
        ref_links=ref_links,
        target_links=target_links,
        project=config.project_name,
        text_in_body=config.text_in_body,
        textrepo_url=textrepo_external_url,
        textrepo_file_versions=textrepo_file_versions,
        logical_coords_for_physical_anchor_per_text=logical_coords_for_physical_anchor_per_text,
        entity_metadata=entity_metadata,
        project_is_editem_project=config.editem_project,
        tier0_type=config.tier0_type,
        entity_for_ref=entity_for_ref,
        letter_id_for_tf_node=letter_id_for_tf_node,
        graphic_url_mapper=config.graphic_url_mapper
    )
    errors.extend(conversion_errors)

    sanity_check_errors = _sanity_check1(web_annotations, config.tier0_type, config.with_facsimiles)
    errors.extend(sanity_check_errors)

    filtered_web_annotations = [
        a for a in web_annotations if
        ('type' in a['body'] and a['body']['type'] not in config.excluded_types)
        or 'type' not in a['body']
    ]
    logger.info(f"{len(filtered_web_annotations)} annotations")
    ut.store_web_annotations(web_annotations=filtered_web_annotations, export_path=f"{export_dir}/web-annotations.json")

    end = time.perf_counter()

    _print_report(config, text_files, filtered_web_annotations, start, end)
    return errors


def _load_entities(path: str) -> (dict[str, dict[str, Any]], list[str]):
    errors = []
    entity_index = {}
    for data_path in glob.glob(f"{path}/*-entity-dict.json"):
        logger.info(f"<= {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            entity_index.update(json.load(f))
    for k, v in entity_index.items():
        if "relation" in v and "ref" in v["relation"]:
            original_ref = v["relation"]["ref"]
            ref_key = original_ref.replace(".xml#", "/")
            if ref_key in entity_index:
                entity_index[k]["relation"]["ref"] = entity_index[ref_key]
            else:
                error = f"{k.replace('/', '.xml#')}: no entity found for ref=\"{original_ref}\""
                logger.error(error)
                errors.append(error)
        entity_index[k] = _rename_type_fields(v)
    return entity_index, errors


def _rename_type_fields(d):
    if isinstance(d, dict):
        new_dict = {}
        for key, value in d.items():
            new_key = "tei:type" if key == "type" else key
            new_dict[new_key] = _rename_type_fields(value)
        return new_dict
    elif isinstance(d, list):
        return [_rename_type_fields(item) for item in d]
    else:
        return d


def _read_token_substitutions(path: str):
    token_subst = {}
    if os.path.exists(path):
        logger.info(f"<= {path}")
        with open(path, encoding='utf8') as f:
            for record in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                token_subst[record['token1']] = record['str']
                token1_num = int(record['token1'])
                break_token = f"{token1_num + 1}"
                token_subst[break_token] = ""
                token_subst[record['token2']] = ""
    return token_subst


def _load_node_for_pos(path: str):
    node_for_pos = {}
    if os.path.exists(path):
        logger.info(f"<= {path}")
        with open(path, encoding='utf8') as f:
            for record in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                node_for_pos[record['position']] = record['node']
    return node_for_pos


def _load_entity_metadata(entity_meta_path):
    if os.path.exists(entity_meta_path):
        logger.info(f"<= {entity_meta_path}")
        with open(entity_meta_path) as f:
            entity_metadata = json.load(f)
    else:
        entity_metadata = None
    return entity_metadata


def _as_class_name(string: str) -> str:
    return string[0].capitalize() + string[1:]


def _read_tf_tokens(text_files) -> dict[str, list[str]]:
    tokens_per_text = {}
    for text_file in text_files:
        text_num = ut.get_file_num(text_file)
        tokens = _read_tokens(text_file)
        tokens_per_text[text_num] = tokens
    return tokens_per_text


def _read_tf_tokens_from_json(text_files):
    tokens_per_text = {}
    for text_file in text_files:
        text_num = ut.get_file_num(text_file)
        logger.info(f"<= {text_file}")
        with open(text_file) as f:
            contents = json.load(f)
        tokens_per_text[text_num] = contents["_ordered_segments"]
    return tokens_per_text


def _read_raw_tf_annotations(anno_file) -> list[TFAnnotation]:
    return [
        TFAnnotation(
            id=row["annoid"],
            type=row["kind"],
            namespace=row["namespace"],
            body=row["body"],
            target=row["target"]
        )
        for row in _read_tsv_records(anno_file)
    ]


def _read_tsv_records(path: str) -> list[dict[str, Any]]:
    # csv.field_size_limit(sys.maxsize)
    logger.info(f"<= {path}")
    with open(path, encoding='utf8') as f:
        records = [row for row in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)]
    return records  # type *is* correct!


def _read_tokens(path: str) -> list[str]:
    logger.info(f"<= {path}")
    with open(path, encoding='utf8') as f:
        tokens = [_token(row) for row in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)]
    return tokens[1:]  # type *is* correct!


def _token(row: list[str]) -> str:
    if row:
        return row[0].replace('\\n', '\n').replace('\\t', '\t')
    else:
        return ""


def _modify_pb_annotations(ia: list[IAnnotation], tokens: list[str]) -> list[IAnnotation]:
    pb_end_anchor = 0
    last_page_in_div = None
    for i, a in enumerate(ia):
        if _is_div_with_pb(a):
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
                prev.text = _text_of(prev, tokens)
            a.type = 'page'
            a.text = _text_of(a, tokens)
    return ia


def _text_of(a, tokens):
    return "".join(tokens[a.begin_anchor:a.end_anchor + 1])


def _is_div_with_pb(a):
    return a.type == "div" \
        and "type" in a.metadata \
        and a.metadata["type"] in ("original", "translation", "postalData")


def _sanity_check(ia: list[IAnnotation]):
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
            if _annotations_overlap(anno1, anno2):
                logger.error("Overlapping Letter annotations: ")
                ic(anno1.id, anno1.metadata, anno1.begin_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.begin_anchor, anno2.end_anchor)

    logger.info("check for overlapping sentence annotations")
    sentence_annotations = [a for a in ia if a.type == 'sentence']
    for i in range(len(sentence_annotations)):
        for j in range(i + 1, len(sentence_annotations)):
            anno1 = sentence_annotations[i]
            anno2 = sentence_annotations[j]
            if _annotations_overlap(anno1, anno2):
                logger.error("Overlapping Sentence annotations: ")
                ic(anno1.id, anno1.metadata, anno1.begin_anchor, anno1.end_anchor)
                ic(anno2.id, anno2.metadata, anno2.begin_anchor, anno2.end_anchor)

    logger.info("check for note annotations without lang")
    note_annotations_without_lang = [a for a in ia if a.type == 'note' and 'lang' not in a.metadata]
    if note_annotations_without_lang:
        logger.error("There are note annotations without lang metadata:")
        ic(note_annotations_without_lang)


def _annotations_overlap(anno1, anno2):
    return (anno1.text_num == anno2.text_num) and (anno1.end_anchor - 1) >= anno2.begin_anchor


def _get_parent_lang(a: IAnnotation, node_parents: dict[str, str], ia_idx: dict[str, IAnnotation]) -> str:
    if a.id in node_parents:
        parent = ia_idx[node_parents[a.id]]
        if 'lang' in parent.metadata:
            return parent.metadata['lang']
        else:
            return _get_parent_lang(parent, node_parents, ia_idx)
    else:
        # logger.warning(f"node {a.id} has no parents, and no metadata.lang -> returning default 'en'")
        return 'en'


def _modify_note_annotations(ia: list[IAnnotation], node_parents: dict[str, str]) -> list[IAnnotation]:
    ia_idx = {a.id: a for a in ia}
    for a in ia:
        if a.type == 'note' and 'lang' not in a.metadata:
            parent_lang = _get_parent_lang(a, node_parents, ia_idx)
            a.metadata['lang'] = parent_lang
            # logger.info(f"enriched note: {a}")
    return ia


def _merge_raw_tf_annotations(
        tf_annotations: list[TFAnnotation],
        anno2node_path: str,
        tokens_per_text,
        show_progress: bool
):
    tf_node_for_annotation_id = {row['annotation']: row['node'] for row in _read_tsv_records(anno2node_path)}
    tf_annotation_idx = {}
    note_target = {}
    node_parents = {}
    ref_links = []
    target_links = []
    bar = None
    if show_progress:
        bar = ut.default_progress_bar(len(tf_annotations))
    for i, tf_annotation in enumerate(tf_annotations):
        if show_progress:
            bar.update(i)  # pyright: ignore
        match tf_annotation.type:
            case 'element':
                _handle_element(tf_annotation, tf_annotation_idx, tokens_per_text)
            # case 'node':
            #     anno_id = a.target
            #     if anno_id in tf_annotation_idx:
            #         tf_annotation_idx[anno_id].tf_node = int(a.body)
            #     # else:
            #     #     logger.warning(f"node target ({anno_id}) not in tf_annotation_idx index")
            #     #     ic(a)
            case 'mark':
                _handle_mark(tf_annotation, note_target, tf_annotation_idx)
            case 'attribute':
                _handle_attribute(tf_annotation, tf_annotation_idx)
            case 'anno':
                _handle_anno(tf_annotation, tf_annotation_idx)
            case 'format':
                _handle_format()
            case 'pi':
                _handle_pi(tf_annotation)
            case 'edge':
                _handle_edge(tf_annotation, node_parents, ref_links, target_links)

            case _:
                logger.warning(f"unhandled type: {tf_annotation.type}")
    print()
    tf_annos = sorted(tf_annotation_idx.values(),
                      key=lambda anno: (int(anno.text_num) * 100_000_000_000 + anno.begin_anchor * 100_000 + (
                              1000 - anno.end_anchor)) * 100_000 + anno.tf_node)
    for tfa in tf_annos:
        tfa.tf_node = tf_node_for_annotation_id[tfa.id]
    # tf_annos = modify_pb_annotations(tf_annos, tokens)
    # ic(node_parents)
    logger.info("modify_note_annotations")
    tf_annos = _modify_note_annotations(tf_annos, node_parents)
    # TODO: convert ptr annotations to annotation linking the ptr target to the body.id of the m:Note with the corresponding id
    # TODO: convert rs annotations to annotation linking the rkd url in metadata.anno to the rd target
    # TODO: convert ref annotations
    logger.info("sanity_check")
    _sanity_check(tf_annos)
    return ref_links, target_links, tf_annos


def _tf_annotations_to_web_annotations(
        tf_annos,
        ref_links,
        target_links,
        project: str,
        text_in_body: bool,
        textrepo_url: str,
        textrepo_file_versions: dict[str, dict[str, str]],
        logical_coords_for_physical_anchor_per_text: dict[str, dict[str, TextCoords]],
        entity_metadata: dict[str, dict[str, str]],
        project_is_editem_project: bool = False,
        tier0_type: Optional[str] = None,
        entity_for_ref: dict[str, Any] = field(default_factory=dict),
        letter_id_for_tf_node: dict[int, str] = field(default_factory=dict),
        graphic_url_mapper: Callable[[str], str] = None
):
    errors = []
    at = AnnotationTransformer(
        project=project,
        textrepo_url=textrepo_url,
        textrepo_versions=textrepo_file_versions,
        text_in_body=text_in_body,
        logical_coords_for_physical_anchor_per_text=logical_coords_for_physical_anchor_per_text,
        entity_metadata=entity_metadata,
        entity_for_ref=entity_for_ref,
        letter_id_for_tf_node=letter_id_for_tf_node,
        graphic_url_mapper=graphic_url_mapper
    )
    logger.info("as_web_annotation")

    tf_node_to_ia_id = {a.tf_node: a.id for a in tf_annos}
    web_annotations = [at.as_web_annotation(a) for a in tf_annos]

    tf_id_to_body_id = {tf_node_to_ia_id[wa["body"]["tf:textfabric_node"]]: wa["body"]["id"] for wa in web_annotations}

    if project == 'suriano':
        letter_body_annotations = _generate_suriano_letter_body_annotations(web_annotations)
        web_annotations.extend(letter_body_annotations)

    if project_is_editem_project and tier0_type:
        _extend_tier0_annotations(web_annotations, tier0_type)

    # ic(ref_links)
    logger.info("ref_annotations")
    ref_annotations = [
        _as_link_anno(from_ia_id, to_ia_id, "referencing", tf_id_to_body_id, project)
        for from_ia_id, to_ia_id in ref_links
    ]
    web_annotations.extend(ref_annotations)

    # ic(target_links)
    logger.info("target_annotations")
    target_annotations = [
        _as_link_anno(from_ia_id, to_ia_id, "targeting", tf_id_to_body_id, project)
        for from_ia_id, to_ia_id in target_links
    ]
    web_annotations.extend(target_annotations)

    if entity_metadata:
        entity_annotations = at.create_entity_annotations()
        web_annotations.extend(entity_annotations)

    if at.errors:
        logger.error("there were conversion errors:")
        for e in sorted(at.errors):
            logger.error(e)
            errors.append(e)
    logger.info("keys_to_camel_case")
    return [cc.keys_to_camel_case(a) for a in web_annotations], errors


def _debug_paragraphs(paragraph_ranges, tokens_per_text):
    ic(paragraph_ranges['0'][0:100])
    for i, r in enumerate(paragraph_ranges['0'][0:100]):
        para_text = "".join(tokens_per_text['0'][r[0]:r[1] + 1])
        print(i)
        print(para_text)
        print()


def _store_logical_text_files(
        export_dir: str,
        paragraph_ranges: dict[str, list[tuple[int, int]]],
        tokens_per_text: dict[str, list[str]],
        node_for_pos: dict[str, str],
        node_subst: dict[str, str]
) -> tuple[list[str], dict[str, dict[str, TextCoords]]]:
    file_paths = []
    logical_coords_for_physical_anchor_per_text = defaultdict(lambda: {})
    for text_num in paragraph_ranges.keys():
        par_segments = []
        no_of_tokens = len(tokens_per_text[text_num])
        # ic(text_num, no_of_tokens)
        for par_range in paragraph_ranges[text_num]:
            par_anchor = len(par_segments)
            para_text = ''
            char_offset = 0
            for physical_anchor in range(par_range[0], min(par_range[1] + 1, no_of_tokens)):
                pos = f"{text_num}:{physical_anchor}"
                node = node_for_pos[pos]
                if node in node_subst:
                    par_token = node_subst[node]
                    para_text += par_token
                    end_char_offset = char_offset + len(par_token) - 1
                else:
                    par_token = tokens_per_text[text_num][physical_anchor].replace("\n", " ")
                    para_text += par_token
                    end_char_offset = char_offset + len(par_token) - 1
                logical_coords_for_physical_anchor_per_text[text_num][physical_anchor] = TextCoords(
                    begin_anchor=par_anchor,
                    begin_char_offset=char_offset,
                    end_anchor=par_anchor,
                    end_char_offset=end_char_offset
                )
                char_offset = end_char_offset + 1
            par_segments.append(para_text)

        json_path = f"{export_dir}/textfile-logical-{text_num}.json"
        file_paths.append(json_path)
        _store_segmented_text(segments=par_segments, store_path=json_path)
    return file_paths, logical_coords_for_physical_anchor_per_text


def _determine_paragraphs(
        tf_annos: list[IAnnotation],
        tokens_per_text: dict[str, list[str]]
) -> dict[str, list[tuple[int, int]]]:
    paragraph_ranges = {}
    current_text_num = -1
    expected_begin_anchor = 0
    for ia in tf_annos:
        if ia.type in paragraph_types:
            # print(ia.text_num, ia.begin_anchor, ia.end_anchor)
            if ia.text_num != current_text_num:
                if current_text_num in tokens_per_text:
                    number_of_tokens_in_current_text = len(tokens_per_text[current_text_num])
                    if number_of_tokens_in_current_text > expected_begin_anchor:
                        paragraph_ranges[current_text_num].append((expected_begin_anchor,
                                                                   number_of_tokens_in_current_text))
                current_text_num = ia.text_num
                paragraph_ranges[current_text_num] = []
                expected_begin_anchor = 0
            if ia.begin_anchor > expected_begin_anchor:
                paragraph_ranges[current_text_num].append((expected_begin_anchor, ia.begin_anchor - 1))
            if ia.begin_anchor < expected_begin_anchor:
                pass
                # if ia.type != "note":
                #     logger.warning(f"nested element {ia.type} ignored for paragraph sectioning")
            else:
                paragraph_ranges[current_text_num].append((ia.begin_anchor, ia.end_anchor))
                expected_begin_anchor = ia.end_anchor + 1
    return paragraph_ranges


def _handle_format():
    # logger.warning("format annotation skipped")
    # ic(a)
    pass


def _handle_edge(tf_annotation: TFAnnotation, node_parents, ref_links, target_links):
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


def _handle_pi(tf_annotation):
    logger.warning("pi annotation skipped")
    ic(tf_annotation)
    pass


def _handle_anno(tf_annotation, tf_annotation_idx):
    element_anno_id = tf_annotation.target
    if element_anno_id in tf_annotation_idx:
        tf_annotation_idx[element_anno_id].metadata["anno"] = tf_annotation.body
    else:
        logger.warning(f"anno target ({element_anno_id}) not in tf_annotation_idx index")
        ic(tf_annotation)


def _handle_attribute(tf_annotation, tf_annotation_idx):
    element_anno_id = tf_annotation.target
    if element_anno_id in tf_annotation_idx:
        (k, v) = tf_annotation.body.split('=', 1)
        if k == 'id':
            k = 'tei:id'
        if k in tf_annotation_idx[element_anno_id].metadata:
            logger.warning(f"extra assignment to {k} for {element_anno_id}")
        tf_annotation_idx[element_anno_id].metadata[k] = v


def _handle_mark(tf_annotation, note_target, tf_annotation_idx):
    note_anno_id = tf_annotation.target
    if note_anno_id in tf_annotation_idx:
        element_anno_id = int(tf_annotation.body)
        note_target[note_anno_id] = element_anno_id
    else:
        logger.warning(f"mark target ({note_anno_id}) not in tf_annotation_idx index")
        ic(tf_annotation)


def _handle_element(a, tf_annotation_idx, tokens_per_text):
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
        begin_anchor = int(match0.group(2))
        end_anchor = begin_anchor
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


def _as_link_anno(
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


def _store_segmented_text(segments: list[str], store_path: str):
    data = {"_ordered_segments": segments}
    logger.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='UTF8') as filehandle:
        json.dump(data, filehandle, indent=4, ensure_ascii=False)


def _dummy_version(text_files):
    textrepo_file_version = {}
    for text_file in text_files:
        file_num = ut.get_file_num(text_file)
        textrepo_file_version[file_num] = {
            'logical': f"placeholder-{file_num}-logical",
            "physical": f"placeholder-{file_num}-physical"
        }
    return textrepo_file_version


def _generate_suriano_letter_body_annotations(web_annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_annotations = [wa for wa in web_annotations if wa['body']['type'] == 'tf:File']
    # ic(len(file_annotations))
    # ic(file_annotations[42])

    relevant_div_annotations = [
        wa for wa in web_annotations
        if wa['body']['type'] == 'tei:Div' and wa['body']['metadata']['type'] != 'notes'
    ]
    # ic(len(relevant_div_annotations))
    # ic(relevant_div_annotations[42])
    iforest = defaultdict(lambda: IntervalTree())
    for da in relevant_div_annotations:
        physical_source, start, end = _physical_range(da)
        iforest[physical_source][start:end] = da

    letter_body_annotations = []

    for fa in file_annotations:
        physical_source, start, end = _physical_range(fa)
        physical_base = physical_source.replace('/contents', '')
        enveloped_annos = [a.data for a in sorted(iforest[physical_source].envelop(start, end))]

        min_physical_start = sys.maxsize
        max_physical_end = 0
        min_logical_start = sys.maxsize
        max_logical_end = 0
        l_begin_char_offset = sys.maxsize
        l_end_char_offset = 0
        for da in enveloped_annos:
            p_selector = da["target"][0]["selector"]
            p_start = p_selector["start"]
            p_end = p_selector["end"]
            l_selector = da["target"][2]["selector"]
            l_start = l_selector["start"]
            l_end = l_selector["end"]
            l_char_start = l_selector["beginCharOffset"]
            l_char_end = l_selector["endCharOffset"]

            if p_start < min_physical_start:
                min_physical_start = p_start
                min_logical_start = l_start
                l_begin_char_offset = l_char_start

            if p_end > max_physical_end:
                max_physical_end = p_end
                max_logical_end = l_end
                l_end_char_offset = l_char_end

        letter_body_annotation = copy.deepcopy(fa)
        letter_body_annotation["id"] = letter_body_annotation["id"] + ":letter_body"
        body = letter_body_annotation['body']
        body.pop('tf:textfabric_node')
        body["id"] = body["id"].replace('file', 'letter_body')
        body["type"] = "LetterBody"
        metadata = body["metadata"]
        metadata["type"] = "LetterBodyMetadata"
        if "prevFile" in metadata:
            metadata['prevLetterBody'] = metadata['prevFile'].replace('file', 'letter_body')
            metadata.pop('prevFile')
        if "nextFile" in metadata:
            metadata['nextLetterBody'] = metadata['nextFile'].replace('file', 'letter_body')
            metadata.pop('nextFile')

        canvas_target = letter_body_annotation["target"][4]

        logical_source, _, _ = _logical_range(fa)
        logical_base = logical_source.replace('/contents', '')
        new_targets = []
        new_targets.extend(
            _text_targets("Text", physical_base, min_physical_start, max_physical_end))
        new_targets.extend(
            _text_targets("LogicalText", logical_base, min_logical_start, max_logical_end, l_begin_char_offset,
                          l_end_char_offset))
        new_targets.append(canvas_target)
        letter_body_annotation['target'] = new_targets
        # ic(letter_body_annotation)
        letter_body_annotations.append(letter_body_annotation)

    return letter_body_annotations


def _extend_tier0_annotations(
        web_annotations: list[dict[str, Any]],
        tier0_type: str):
    # the annotations to extend from
    tier0_annotations = [wa for wa in web_annotations if wa['body']['type'] == tier0_type]

    # the annotations to copy targets from
    text_annotations = [wa for wa in web_annotations if wa['body']['type'] == 'tei:Text']
    iforest = defaultdict(lambda: IntervalTree())
    for da in text_annotations:
        physical_source, start, end = _physical_range(da)
        iforest[physical_source][start:end] = da

    # the annotations to get pageUrl, xywh from
    page_annotations = [wa for wa in web_annotations if wa['body']['type'] == 'tf:Page']
    page_forest = defaultdict(lambda: IntervalTree())
    for pa in page_annotations:
        physical_source, start, end = _physical_range(pa)
        if start == end:
            logger.warning(f'tf:Page without text: {pa}')
            end = start + 1
        page_forest[physical_source][start:end] = pa

    for t0_annotation in tier0_annotations:
        physical_source, start, end = _physical_range(t0_annotation)
        physical_base = physical_source.replace('/contents', '')
        enveloped_text_annos = [a.data for a in sorted(iforest[physical_source].envelop(start, end))]
        text_anno = enveloped_text_annos[0]

        enveloped_page_annos = [a.data for a in sorted(page_forest[physical_source].envelop(start, end))]

        min_physical_start = sys.maxsize
        max_physical_end = 0
        min_logical_start = sys.maxsize
        max_logical_end = 0
        l_begin_char_offset = sys.maxsize
        l_end_char_offset = 0
        for da in enveloped_text_annos:
            p_selector = da["target"][0]["selector"]
            p_start = p_selector["start"]
            p_end = p_selector["end"]
            l_selector = da["target"][2]["selector"]
            l_start = l_selector["start"]
            l_end = l_selector["end"]
            l_char_start = l_selector["beginCharOffset"]
            l_char_end = l_selector["endCharOffset"]

            if p_start < min_physical_start:
                min_physical_start = p_start
                min_logical_start = l_start
                l_begin_char_offset = l_char_start

            if p_end > max_physical_end:
                max_physical_end = p_end
                max_logical_end = l_end
                l_end_char_offset = l_char_end

        logical_source, _, _ = _logical_range(text_anno)
        logical_base = logical_source.replace('/contents', '')
        new_targets = []
        new_targets.extend(
            _text_targets("Text", physical_base, min_physical_start, max_physical_end))
        new_targets.extend(
            _text_targets("LogicalText", logical_base, min_logical_start, max_logical_end, l_begin_char_offset,
                          l_end_char_offset))
        for pa in enveloped_page_annos:
            canvas_targets = [t for t in pa["target"] if t['type'] == 'Canvas']
            if len(canvas_targets) > 1:
                raise Exception("unexpected situation: multiple canvas targets")
            canvas_target = canvas_targets[0]
            if canvas_target not in new_targets:
                new_targets.append(canvas_target)

            pa_metadata = pa["body"]["metadata"]
            page_url = pa_metadata["pageUrl"]
            xywh = pa_metadata["xywh"]
            for it in _image_targets(page_url, xywh):
                if it not in new_targets:  # avoid duplicate image targets
                    new_targets.append(it)

        t0_annotation['target'] += [nt for nt in new_targets if nt["type"] in ["Canvas", "Image"]]


def _physical_range(wa):
    source = wa["target"][0]["source"]
    selector = wa["target"][0]["selector"]
    start = selector["start"]
    end = selector["end"]
    return source, start, end


def _logical_range(wa):
    source = wa["target"][2]["source"]
    selector = wa["target"][2]["selector"]
    start = selector["start"]
    end = selector["end"]
    return source, start, end


def _text_targets(target_type, base, start_anchor, end_anchor, char_start=None, char_end=None):
    selector = {
        "type": "tt:TextAnchorSelector",
        "start": start_anchor,
        "end": end_anchor
    }
    if char_start:
        selector['beginCharOffset'] = char_start
        selector['endCharOffset'] = char_end
        segments_source = f"{base.replace('rest', 'view')}/segments/index/{start_anchor}/{char_start}/{end_anchor}/{char_end}"
    else:
        segments_source = f"{base.replace('rest', 'view')}/segments/index/{start_anchor}/{end_anchor}"
    return [
        {
            "source": f"{base}/contents",
            "type": target_type,
            "selector": selector
        },
        {
            "source": segments_source,
            "type": target_type
        }
    ]


def _image_targets(iiif_url: str, xywh: str) -> list[dict[str, Any]]:
    iiif_base_url = re.sub(r"/full/.*", '', iiif_url)
    return [simple_image_target(iiif_base_url, xywh), image_target(iiif_url=iiif_url, xywh=xywh)]


def _has_nested_field_with_value(d: dict[str, Any], nested_field: str, value: Any) -> bool:
    def loop(ld: dict[str, Any], field_path: list[str], expected_value: Any) -> bool:
        field_name = field_path[0]
        if len(field_path) == 1:
            return field_name in ld and ld[field_name] == expected_value
        elif field_name in ld and isinstance(ld[field_name], dict):
            return loop(ld[field_name], field_path[1:], expected_value)
        else:
            return False

    return loop(d, nested_field.split("."), value)


def _sanity_check1(web_annotations: list, tier0_type: str, expect_manifest: bool) -> list[str]:
    errors = []
    tier0_annotations = [a for a in web_annotations if _has_nested_field_with_value(a, "body.type", tier0_type)]
    if not tier0_annotations:
        error = f"no tier0 annotations found, tier0 = '{tier0_type}'"
        logger.error(error)
        errors.append(error)
    else:
        if expect_manifest:
            for a in tier0_annotations:
                if 'manifest' not in a['body']['metadata']:
                    error = f"missing required body.metadata.manifest field for {a}"
                    logger.error(error)
                    errors.append(error)
    return errors


def _print_report(config, text_files, filtered_web_annotations, start, end):
    print(f"untangling {config.project_name} took {end - start:0.4f} seconds")
    print(f"text files: {len(text_files)}")
    print(f"annotations: {len(filtered_web_annotations)}")
    print(f"tier0 = {config.tier0_type}")
    ut.show_annotation_counts(filtered_web_annotations, config.excluded_types)
