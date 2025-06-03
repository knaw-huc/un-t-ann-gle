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
from typing import Any, Union, List, Optional

from icecream import ic
from intervaltree import IntervalTree
from loguru import logger

from untanngle import camel_casing as cc
from untanngle import utils as ut
from untanngle.annotations import simple_image_target, image_target

file_num_pattern = re.compile(r".*-(\d+).tsv")
file_num_pattern_from_json = re.compile(r".*-(\d+).json")
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
    "note",
    "num",
    "p",
    "person",
    "resp",
    "settlement",
    "title",
}


@dataclass
class TFUntangleConfig:
    project_name: str
    data_path: str
    export_path: str
    tier0_type: str
    excluded_types: list[str]
    textsurf_base_uri_internal: Optional[str] = None #full url (including any project part), no trailing slash. This may also be a directory on the local filesystem!
    textsurf_base_uri_external: Optional[str] = None #full url (including any project part), no trailing slash
    text_in_body: bool = False
    with_facsimiles: bool = True
    show_progress: bool = False
    log_file_path: Optional[str] = None
    editem_project: bool = False
    apparatus_data_directory: Optional[str] = None
    intro_files: list[str] = field(default_factory=list)


@dataclass
class TFAnnotation:
    id: str
    namespace: str
    type: str
    body: str
    target: str

@dataclass
class Offset:
    start: int
    end: int

@dataclass
class IAnnotation:
    id: str = ""
    namespace: str = ""
    type: str = ""
    tf_node: int = 0
    text: str = ""
    char_offset_phys: Offset = field(default_factory= lambda: Offset(0,0))
    char_offset_log: Offset = field(default_factory= lambda: Offset(0,0))
    text_num: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def physical_to_logical(self, physical_to_logical: dict[int,int]):
        """Computes logical coordinates from physical ones, given a mapping (generated from the same annotations)"""
        self.char_offset_log.start = physical_to_logical[self.char_offset_phys.start]
        self.char_offset_log.end = physical_to_logical[self.char_offset_phys.end]

@dataclass
class AnnotationTransformer:
    project: str
    textsurf_url: str
    text_in_body: bool
    physical_to_logical: dict[str, dict[int,int]]
    entity_metadata: dict[str, dict[str, str]]
    entity_for_ref: dict[str, dict[str, Any]] = field(default_factory=dict)

    errors = set()

    def as_web_annotation(self, ia: IAnnotation) -> dict[str, Any]:
        body_type = f"{ia.namespace}:{_as_class_name(ia.type)}"
        text_num = ia.text_num
        body_id = f"urn:{self.project}:{ia.type}:{ia.tf_node}"
        #logger.debug(f"Physical->Logical: {ia.char_offset_phys}")
        ia.physical_to_logical(self.physical_to_logical[text_num])
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
                    "source": f"{self.textsurf_url}/{text_num}",
                    "type": "Text",
                    "selector": {
                        "type": "TextPositionSelector",
                        "start": ia.char_offset_phys.start,
                        "end": ia.char_offset_phys.end
                    }
                },
                {
                    "source": f"{self.textsurf_url}/{text_num}?char={ia.char_offset_phys.start},{ia.char_offset_phys.end}",
                    "type": "Text"
                },
                {
                    "source": f"{self.textsurf_url}/{text_num}.logical",
                    "type": "LogicalText",
                    "selector": {
                        "type": "TextPositionSelector",
                        "start": ia.char_offset_log.start,
                        "end": ia.char_offset_log.end
                    }
                },
                {
                    "source": f"{self.textsurf_url}/{text_num}.logical?char={ia.char_offset_log.start},{ia.char_offset_log.end}",
                    "type": "LogicalText"
                }
            ]
        }

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
                prevNode = ia.metadata["prev"]
                metadata.pop("prev")
                metadata[f"prev{ia.type.capitalize()}"] = f"urn:{self.project}:{ia.type}:{prevNode}"

            if "next" in ia.metadata:
                nextNode = ia.metadata["next"]
                metadata.pop("next")
                metadata[f"next{ia.type.capitalize()}"] = f"urn:{self.project}:{ia.type}:{nextNode}"

            if "eid" in ia.metadata:
                entity_id = f"{ia.metadata['eid']}-{ia.metadata['kind']}"
                metadata["entityId"] = f"urn:{self.project}:entity:{entity_id}"
                if self.entity_metadata:
                    metadata["details"] = [
                        {"label": mk, "value": mv}
                        for mk, mv
                        in self.entity_metadata[entity_id].items()
                    ]

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

    def _normalized_metadata_value(self, value: str) -> list[dict[str,Any]] | str:
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
            return {ref:None}


def untangle_tf_export(config: TFUntangleConfig):
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
    entity_for_ref = _load_entities(f"{config.apparatus_data_directory}")
    node_for_pos = _load_node_for_pos(pos_to_node_path) #TODO: not used anymore, delete?
    #TODO: these are not migrated yet! currently left unused! it contains dehyphenation substitutions
    token_subst = _read_token_substitutions(logical_pairs_path)

    out_files = []
    text_nums = []
    texts: dict[str,str] = {}
    segments_to_char_per_file: dict[str, list[int]] = {}
    for tsv in text_files:
        text_num = _get_file_num(tsv)
        text_nums += text_num
        text_path = f"{export_dir}/{text_num}.txt" #physical texts
        segments = _read_tokens(tsv)
        text= "".join(segments)
        texts[text_num] = "".join(segments)
        _store_text(text=text, store_path=text_path)
        segments_to_char_offsets = _segments_to_char_offsets(segments)
        segments_to_char_per_file[text_num] = segments_to_char_offsets
        out_files.append(text_path)


    tokens_per_file = _read_tf_tokens(text_files)
    raw_tf_annotations: list[TFAnnotation] = []
    for anno_file in anno_files:
        raw_tf_annotations.extend(_read_raw_tf_annotations(anno_file))

    ref_links, target_links, tf_annos = _merge_raw_tf_annotations(raw_tf_annotations, anno2node_path, 
                                                                  tokens_per_file, segments_to_char_per_file, config.show_progress)

    paragraph_ranges = _determine_paragraphs(tf_annos, tokens_per_file, segments_to_char_per_file)
    # debug_paragraphs(paragraph_ranges, tokens_per_text)

    logical_file_paths, physical_to_logical = _store_logical_text_files(
        export_dir,
        paragraph_ranges,
        texts,
    )
    out_files.extend(logical_file_paths)

    if config.textsurf_base_uri_internal:
        ut.upload_to_textsurf(config.textsurf_base_uri_internal, tf_text_files=out_files)
    else:
        logger.warning("No textsurf URL or local directory specified, texts won't be available")

    textsurf_external_url = config.textsurf_base_uri_external if config.textsurf_base_uri_external else config.textsurf_base_uri_internal
    assert textsurf_external_url is not None
    web_annotations = _tf_annotations_to_web_annotations(
        tf_annos=tf_annos,
        ref_links=ref_links,
        target_links=target_links,
        project=config.project_name,
        text_in_body=config.text_in_body,
        textsurf_url=textsurf_external_url,
        physical_to_logical=physical_to_logical,
        entity_metadata=entity_metadata,
        project_is_editem_project=config.editem_project,
        tier0_type=config.tier0_type,
        entity_for_ref=entity_for_ref
    )

    merged_web_annotations = _merge_intro_texts(web_annotations, config.intro_files)
    _sanity_check1(merged_web_annotations, config.tier0_type, config.with_facsimiles)
    filtered_web_annotations = [
        a for a in merged_web_annotations if
        ('type' in a['body'] and a['body']['type'] not in config.excluded_types)
        or 'type' not in a['body']
    ]
    logger.info(f"{len(filtered_web_annotations)} annotations")
    ut.store_web_annotations(web_annotations=filtered_web_annotations, export_path=f"{export_dir}/web-annotations.json")

    end = time.perf_counter()

    _print_report(config, text_files, filtered_web_annotations, start, end)


def _load_entities(path: str) -> dict[str, dict[str, Any]]:
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
                logger.error(f"{k.replace('/', '.xml#')}: no entity found for ref=\"{original_ref}\"")
        entity_index[k] = _rename_type_fields(v)
    return entity_index


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


def _load_node_for_pos(path: str) -> dict[str,int]:
    node_for_pos = {}
    if os.path.exists(path):
        logger.info(f"<= {path}")
        with open(path, encoding='utf8') as f:
            for record in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                node_for_pos[record['position']] = int(record['node'])
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
        text_num = _get_file_num(text_file)
        tokens = _read_tokens(text_file)
        tokens_per_text[text_num] = tokens
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

def _segments_to_char_offsets(segments: list[str]) -> list[int]:
    begin_char_offsets = []
    offset = 0
    for segment in segments:
        begin_char_offsets.append(offset)
        offset += len(segment)
    #add one final entry, the begin position of which is the end of the text. 
    #(so there will be |segments| + 1  entries in the result)
    begin_char_offsets.append(offset)
    return begin_char_offsets



def _token(row: list[str]) -> str:
    if row:
        return row[0].replace('\\n', '\n').replace('\\t', '\t')
    else:
        return ""


def _sanity_check(ia: list[IAnnotation]):
    logger.info("check for annotations_with_invalid_character offsets_range")
    annotations_with_invalid_char_range = [a for a in ia if a.char_offset_phys.start > a.char_offset_phys.end]
    if annotations_with_invalid_char_range:
        logger.error("There are annotations with invalid char range:")
        ic(annotations_with_invalid_char_range)

    logger.info("check for overlapping letter annotations")
    letter_annotations = [a for a in ia if a.type == 'letter']
    for i in range(len(letter_annotations)):
        for j in range(i + 1, len(letter_annotations)):
            anno1 = letter_annotations[i]
            anno2 = letter_annotations[j]
            if _annotations_overlap(anno1, anno2):
                logger.error("Overlapping Letter annotations: ")
                ic(anno1.id, anno1.metadata, anno1.char_offset_phys.start, anno1.char_offset_phys.end)
                ic(anno2.id, anno2.metadata, anno2.char_offset_phys.start, anno2.char_offset_phys.end)

    logger.info("check for overlapping sentence annotations")
    sentence_annotations = [a for a in ia if a.type == 'sentence']
    for i in range(len(sentence_annotations)):
        for j in range(i + 1, len(sentence_annotations)):
            anno1 = sentence_annotations[i]
            anno2 = sentence_annotations[j]
            if _annotations_overlap(anno1, anno2):
                logger.error("Overlapping Sentence annotations: ")
                ic(anno1.id, anno1.metadata, anno1.char_offset_phys.start, anno1.char_offset_phys.end)
                ic(anno2.id, anno2.metadata, anno2.char_offset_phys.start, anno2.char_offset_phys.end)

    logger.info("check for note annotations without lang")
    note_annotations_without_lang = [a for a in ia if a.type == 'note' and 'lang' not in a.metadata]
    if note_annotations_without_lang:
        logger.error("There are note annotations without lang metadata:")
        ic(note_annotations_without_lang)


def _annotations_overlap(anno1, anno2):
    return (anno1.text_num == anno2.text_num) and (\
        ((anno1.char_offset_phys.end_char_offset >= anno2.char_offset_phys.begin_char_offset) and (anno1.char_offset_phys.end_char_offset <= anno2.char_offset_phys.end_char_offset)) or \
        ((anno2.char_offset_phys.end_char_offset >= anno1.char_offset_phys.begin_char_offset) and (anno2.char_offset_phys.end_char_offset <= anno1.char_offset_phys.end_char_offset)))


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


def _merge_raw_tf_annotations(tf_annotations: list[TFAnnotation], anno2node_path: str,  tokens_per_text: dict[str, list[str]], segments_to_char_per_text: dict[str, list[int]], show_progress: bool):
    tf_node_for_annotation_id = {row['annotation']: row['node'] for row in _read_tsv_records(anno2node_path)}
    tf_annotation_idx = {}
    note_target = {}
    node_parents = {}
    ref_links = []
    target_links = []
    if show_progress:
        bar = ut.default_progress_bar(len(tf_annotations))
    for i, tf_annotation in enumerate(tf_annotations):
        if show_progress:
            bar.update(i) #pyright: ignore
        match tf_annotation.type:
            case 'element':
                _handle_element(tf_annotation, tf_annotation_idx, tokens_per_text, segments_to_char_per_text)
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
                      key=lambda anno: (int(anno.text_num),  anno.char_offset_phys.start, anno.char_offset_phys.end, anno.tf_node) )
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
        tf_annos: list[IAnnotation],
        ref_links,
        target_links,
        project: str,
        text_in_body: bool,
        textsurf_url: str,
        physical_to_logical: dict[str, dict[int,int]],
        entity_metadata: dict[str, dict[str, str]],
        project_is_editem_project: bool = False,
        tier0_type: Optional[str] = None,
        entity_for_ref: dict[str, Any] = field(default_factory=dict),
):
    at = AnnotationTransformer(
        project=project,
        textsurf_url=textsurf_url,
        text_in_body=text_in_body,
        physical_to_logical=physical_to_logical,
        entity_metadata=entity_metadata,
        entity_for_ref=entity_for_ref
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
    logger.info("keys_to_camel_case")
    return [cc.keys_to_camel_case(a) for a in web_annotations]


def _debug_paragraphs(paragraph_ranges, tokens_per_text):
    ic(paragraph_ranges['0'][0:100])
    for i, r in enumerate(paragraph_ranges['0'][0:100]):
        para_text = "".join(tokens_per_text['0'][r[0]:r[1] + 1])
        print(i)
        print(para_text)
        print()


def _store_logical_text_files(
        export_dir: str,
        paragraph_ranges: dict[str, list[Offset]], # int = tf_node_id
        texts: dict[str,str],
) -> tuple[list[str], dict[str, dict[int,int]]]:
    file_paths = []
    physical_to_logical: dict[str, dict[int,int]] = {} #maps a physical coordinate to a logical one, per text (str)
    for text_num in paragraph_ranges.keys():
        full_text_logical = ""
        physical_to_logical[text_num] = {}
        previous_range: Optional[Offset] = None
        for par_range in paragraph_ranges[text_num]:
            assert par_range.end > par_range.start

            #if text_num == "0":
            #    logger.debug(f"Computing logical text {text_num} for paragraph range {par_range}")
            if previous_range and par_range.start > previous_range.end:
                #there's a gap in the text not covered by anything paragraph-like, add it
                full_text_logical += texts[text_num][previous_range.end:par_range.start]

            para_text_physical = texts[text_num][par_range.start:par_range.end]
            #this isn't the most efficient yet, as it maps every character:
            for i, c in enumerate(para_text_physical):
                physical_to_logical[text_num][par_range.start + i] = len(full_text_logical)
                if c in ('\n',' '):
                    full_text_logical += " "
                else:
                    full_text_logical += c
            physical_to_logical[text_num][par_range.end] = len(full_text_logical)

            previous_range = par_range

        text_path = f"{export_dir}/{text_num}.logical.txt"
        file_paths.append(text_path)
        _store_text(full_text_logical, store_path=text_path)
    return file_paths, physical_to_logical



def _determine_paragraphs(
        tf_annos: list[IAnnotation],
        tokens_per_text: dict[str, list[str]],
        segments_to_char_per_text: dict[str, list[int]],
) -> dict[str, list[Offset]]:
    paragraph_ranges = {}
    current_text_num = -1
    expected_begin_offset = 0
    for ia in tf_annos:
        if ia.type in paragraph_types:
            if ia.text_num != current_text_num:
                if current_text_num in tokens_per_text:
                    #new text
                    text_length = segments_to_char_per_text[current_text_num][-1]
                    if text_length > expected_begin_offset:
                        #add last leftover from previous text
                        paragraph_ranges[current_text_num].append(
                            Offset(expected_begin_offset,text_length)
                        )
                current_text_num = ia.text_num
                paragraph_ranges[current_text_num] = []
                expected_begin_offset = 0
            if ia.char_offset_phys.start > expected_begin_offset:
                paragraph_ranges[current_text_num].append(
                    Offset(expected_begin_offset, ia.char_offset_phys.start)
                )
            if ia.char_offset_phys.start < expected_begin_offset:
                pass
                # if ia.type != "note":
                #     logger.warning(f"nested element {ia.type} ignored for paragraph sectioning")
            elif ia.char_offset_phys.end > ia.char_offset_phys.start:
                paragraph_ranges[current_text_num].append(
                    Offset(ia.char_offset_phys.start, ia.char_offset_phys.end)
                )
                expected_begin_offset = ia.char_offset_phys.end
    return paragraph_ranges


def _handle_format():
    # logger.warning("format annotation skipped")
    # ic(a)
    pass


def _handle_edge(tf_annotation, node_parents, ref_links, target_links):
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


def _handle_element(a, tf_annotation_idx, tokens_per_text: dict[str, list[str]], segments_to_char_per_text: dict[str, list[int]]):
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
        begin_char_offset = segments_to_char_per_text[text_num][begin_anchor]
        end_char_offset = segments_to_char_per_text[text_num][end_anchor]
        #if text_num == '0':
        #    logger.debug(f"handle_element(1) {begin_char_offset}:{end_char_offset} -- {text}")
        tf_annos = IAnnotation(id=a.id,
                               namespace=a.namespace,
                               type=a.body,
                               text=text,
                               text_num=text_num,
                               char_offset_phys= Offset(begin_char_offset, end_char_offset),
                               )
        tf_annotation_idx[a.id] = tf_annos
    elif match0:
        text_num = match0.group(1)
        begin_anchor = int(match0.group(2))
        text = "".join(tokens_per_text[text_num][begin_anchor])
        begin_char_offset = segments_to_char_per_text[text_num][begin_anchor]
        end_char_offset = segments_to_char_per_text[text_num][begin_anchor+1]
        #if text_num == '0':
        #    logger.debug(f"handle_element(0) {begin_char_offset}:{end_char_offset} -- {text}")
        tf_annos = IAnnotation(id=a.id,
                               namespace=a.namespace,
                               type=a.body,
                               text=text,
                               text_num=text_num,
                               char_offset_phys= Offset(begin_char_offset, end_char_offset))
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


def _get_file_num(tf_text_file: str) -> str:
    match = file_num_pattern.match(tf_text_file)
    if match:
        return match.group(1)
    else:
        match = file_num_pattern_from_json.match(tf_text_file)
        if match:
            return match.group(1)
        else:
            return ""

def _store_text(text: str, store_path: str):
    """Stores text as a simple plain text file with all segments concatenated."""
    logger.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='utf-8') as filehandle:
        filehandle.write(text)

#TODO: Not migrated yet (proycon)
def _generate_suriano_letter_body_annotations(web_annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raise NotImplementedError("Suriano is not ported yet to the new textselector/textsurf!")
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
    """Adds relevant targets to tier0 annotations"""
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
        enveloped_text_annos = [a.data for a in sorted(iforest[physical_source].envelop(start, end))]
        text_anno = enveloped_text_annos[0]

        enveloped_page_annos = [a.data for a in sorted(page_forest[physical_source].envelop(start, end))]

        min_physical_start = sys.maxsize
        max_physical_end = 0
        min_logical_start = sys.maxsize
        max_logical_end = 0
        for da in enveloped_text_annos:
            p_selector = da["target"][0]["selector"]
            p_start = p_selector["start"]
            p_end = p_selector["end"]
            l_selector = da["target"][2]["selector"]
            l_start = l_selector["start"]
            l_end = l_selector["end"]

            if p_start < min_physical_start:
                min_physical_start = p_start
                min_logical_start = l_start

            if p_end > max_physical_end:
                max_physical_end = p_end
                max_logical_end = l_end

        logical_source, _, _ = _logical_range(text_anno)
        new_targets = []
        new_targets.extend(
            _text_targets("Text", physical_source, min_physical_start, max_physical_end))
        new_targets.extend(
            _text_targets("LogicalText", logical_source, min_logical_start, max_logical_end))
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


def _text_targets(target_type, base_url, start,end):
    selector = {
        "type": "TextPositionSelector",
        "start": start,
        "end": end
    }
    return [
        {
            "source": f"{base_url}",
            "type": target_type,
            "selector": selector
        },
        {
            "source": f"{base_url}?char={start},{end}",
            "type": target_type
        }
    ]


def _image_targets(iiif_url: str, xywh: str) -> list[dict[str, Any]]:
    iiif_base_url = re.sub(r"/full/.*", '', iiif_url)
    return [simple_image_target(iiif_base_url, xywh), image_target(iiif_url=iiif_url, xywh=xywh)]



@dataclass
class IntroTextMetadata:
    source: str
    intro_nl: Offset
    intro_nl_annotations: list[dict[str, Any]]
    intro_en: Offset
    intro_en_annotations: list[dict[str, Any]]
    notes_nl: Optional[Offset] = None
    notes_nl_annotations: list[dict[str, Any]] = field(default_factory=list)
    notes_en: Optional[Offset] = None
    notes_en_annotations: list[dict[str, Any]] = field(default_factory=list)


def _merge_intro_texts(web_annotations: list[dict[str, Any]], intro_files: list[str]) -> list[dict[str, Any]]:
    intro_file_annotations = [_file_annotation(web_annotations, intro_file) for intro_file in intro_files]
    ic(intro_file_annotations)
    tr_targets = [
        (ifa["target"][0]["source"], ifa["target"][0]["selector"]["start"], ifa["target"][0]["selector"]["end"])
        for ifa in intro_file_annotations
    ]
    ic(tr_targets)
    target_sources = [ta[0] for ta in tr_targets]

    # assumption: every intro text has:
    # 1 <div xml:lang="nl">
    # 1 <div xml:lang="en">
    # 0 or 1 <listAnnotation type="notes" xml:lang="nl">
    # 0 or 1 <listAnnotation type="notes" xml:lang="en">
    intro_text_metadata_list: List[IntroTextMetadata] = []
    for ifa in intro_file_annotations:
        source = ifa["target"][0]["source"]
        annotations_with_target_source = [
            a for a in web_annotations
            if _has_target_source_in(a, [source])
        ]
        intro_nl_offset = _offset(annotations_with_target_source, "tei:Div", source, "nl")
        intro_nl_annotations = _annotations_within_range(annotations_with_target_source, source, intro_nl_offset)

        intro_en_offset = _offset(annotations_with_target_source, "tei:Div", source, "en")
        intro_en_annotations = _annotations_within_range(annotations_with_target_source, source, intro_en_offset)

        notes_nl_offset = _offset(annotations_with_target_source, "tei:ListAnnotation", source, "nl")
        notes_nl_annotations = _annotations_within_range(annotations_with_target_source, source, notes_nl_offset)

        notes_en_offset = _offset(annotations_with_target_source, "tei:ListAnnotation", source, "en")
        notes_en_annotations = _annotations_within_range(annotations_with_target_source, source, notes_en_offset)
        
        if isinstance(intro_nl_offset, Offset) and isinstance(intro_en_offset, Offset):
            intro_text_metadata_list.append(
                IntroTextMetadata(
                    source=source,
                    intro_nl=intro_nl_offset,
                    intro_nl_annotations=intro_nl_annotations,
                    intro_en=intro_en_offset,
                    intro_en_annotations=intro_en_annotations,
                    notes_nl=notes_nl_offset,
                    notes_nl_annotations=notes_nl_annotations,
                    notes_en=notes_en_offset,
                    notes_en_annotations=notes_en_annotations,
                )
            )

    ic(intro_text_metadata_list)



    web_annotations_with_intro_targets = [wa for wa in web_annotations if _has_target_source_in(wa, target_sources)]
    ic(len(web_annotations_with_intro_targets))
    return [a for a in web_annotations if a not in web_annotations_with_intro_targets]


def _offset(web_annotations, body_type: str, source: str, lang: str) -> Union[Offset, None]:
    relevant_annotations = [
        a for a in web_annotations if
        _has_nested_field_with_value(a, "body.type", body_type)
        and _has_nested_field_with_value(a, "body.metadata.lang", lang)
        and _has_target_source_in(a, [source])
    ]

    i = len(relevant_annotations)
    if i > 1:
        raise Exception(f"expected one <{body_type} xml:lang=\"{lang}\"/>>, found {i}")
    elif i == 0:
        return None

    target = [
        t for t in (relevant_annotations[0]["target"])
        if _has_nested_field_with_value(t, "source", source)
    ][0]
    selector = target["selector"]
    return Offset(selector["start"], selector["end"])


def _annotations_within_range(
        web_annotations: list[dict[str, Any]],
        source: str,
        offset: Optional[Offset]
) -> list[dict[str, Any]]:
    if offset:
        return [a for a in web_annotations if _has_target_in_range(a, source, offset)]
    else:
        return []


def _has_target_in_range(wa: dict[str, Any], source: str, offset: Offset) -> bool:
    target = [
        t for t in (wa["target"])
        if _has_nested_field_with_value(t, "source", source)
    ][0]
    selector = target["selector"]
    start = selector["start"]
    end = selector["end"]
    return offset.start <= start <= offset.end and offset.start <= end <= offset.end


def _file_annotation(web_annotations: list[dict[str, Any]], intro_file: str) -> dict[str, Any]:
    file_annotations = [a for a in web_annotations if
                        _has_nested_field_with_value(a, "body.type", "tf:File") and
                        _has_nested_field_with_value(a, "body.metadata.file", intro_file)
                        ]
    if len(file_annotations) != 1:
        raise Exception("unexpected situation: multiple file annotations, or none")
    else:
        return file_annotations[0]


def _has_nested_field_with_value(d: dict[str, Any], nested_field: str, value: Any) -> bool:
    def loop(d: dict[str, Any], field_path: list[str], expected_value: Any) -> bool:
        field_name = field_path[0]
        if len(field_path) == 1:
            return field_name in d and d[field_name] == expected_value
        elif field_name in d and isinstance(d[field_name], dict):
            return loop(d[field_name], field_path[1:], expected_value)
        else:
            return False

    return loop(d, nested_field.split("."), value)


def _has_target_source_in(wa: dict[str, Any], target_sources: list[str]) -> bool:
    targets = wa["target"]
    if isinstance(targets, list):
        sources = [t["source"] for t in targets]
        return bool(set(sources) & set(target_sources))
    else:
        if "source" in targets:
            return targets["source"] in target_sources
        else:
            return targets in target_sources


def _sanity_check1(web_annotations: list, tier0_type: str, expect_manifest: bool):
    tier0_annotations = [a for a in web_annotations if _has_nested_field_with_value(a, "body.type", tier0_type)]
    if not tier0_annotations:
        logger.error(f"no tier0 annotations found, tier0 = '{tier0_type}'")
    else:
        if expect_manifest:
            for a in tier0_annotations:
                if 'manifest' not in a['body']['metadata']:
                    logger.error(f"missing required body.metadata.manifest field for {a}")


def _print_report(config, text_files, filtered_web_annotations, start, end):
    print(f"untangling {config.project_name} took {end - start:0.4f} seconds")
    print(f"text files: {len(text_files)}")
    print(f"annotations: {len(filtered_web_annotations)}")
    print(f"tier0 = {config.tier0_type}")
    ut.show_annotation_counts(filtered_web_annotations, config.excluded_types)
