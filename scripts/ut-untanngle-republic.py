#!/usr/bin/env python3
import argparse
import datetime
import glob
import json
import logging
import re
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import List, Dict, Any

from alive_progress import alive_bar
from loguru import logger
from stam import AnnotationStore, Selector, Offset, TextSelectionOperator

from untanngle.annotation import asearch
from untanngle.textservice import segmentedtext
from untanngle.textservice.segmentedtext import IndexedSegmentedText

# untanngle process

# selected classes that refer to persons
attendant_classes = ('president', 'delegate', 'raadpensionaris')

# constants used for compilation of iiif urls
region_pattern = re.compile(r'(.jpg/)(\d+),(\d+),(\d+),(\d+)')
image_id_pattern = re.compile(r'(images.diginfra.net/iiif/)(.*)(/)(\d+),(\d+),(\d+),(\d+)')
iiif_base = 'https://images.diginfra.net/iiif/'
iiif_extension = '/max/0/default.jpg'

resolution_es_index = "https://annotation.republic-caf.diginfra.org/elasticsearch/full_resolutions"
session_es_index = "https://annotation.republic-caf.diginfra.org/elasticsearch/session_lines"

logical_anchor_range_for_line_anchor = defaultdict(lambda: LogicalAnchorRange(0, 0, 0, 0))


class AnnotationsWrapper:
    def __init__(self, annotations: List):
        self.annotation_idx = {a["id"]: a for a in annotations}
        max_anchor = max([a['end_anchor'] for a in annotations]) + 1
        store = AnnotationStore(id=uuid.uuid4())
        resource = store.add_resource(id="dummy", text="*" * max_anchor)
        annotation_set = store.add_annotationset(id="type_set")
        annotation_set.add_key("type")
        for a in annotations:
            a_type = a['type']
            type_data = annotation_set.add_data(key="type", value=a_type)
            store.annotate(
                id=a['id'],
                target=Selector.textselector(resource, Offset.simple(a['begin_anchor'], a['end_anchor'] + 1)),
                data=type_data
            )
        # store.set_filename("out/store.json")
        # store.save()
        self.resource = resource

    @cache
    def get_annotations_overlapping_with_anchor_range(self, begin_anchor, end_anchor):
        selection = self.resource.textselection(Offset.simple(begin_anchor, end_anchor + 1))
        overlapping = [self.annotation_idx[a.id()] for a in
                       selection.find_annotations(TextSelectionOperator.overlaps())]
        exact = [self.annotation_idx[a.id()] for a in selection.annotations()]
        return overlapping + exact


@dataclass
class LogicalAnchorRange:
    begin_logical_anchor: int
    begin_char_offset: int
    end_logical_anchor: int
    end_char_offset: int


class AnnTypes(Enum):
    SESSION = "session"
    TEXTREGION = "text_region"
    LINE = "line"
    RESOLUTION = "resolution"
    PARAGRAPH = "republic_paragraph"
    RESOLUTION_REVIEW = "reviewed"
    ATTENDANCE_LIST = "attendance_list"
    PAGE = "page"
    ATTENDANT = "attendant"
    SCAN = "scan"


line_based_types = [
    AnnTypes.SESSION,
    AnnTypes.PARAGRAPH,
    AnnTypes.RESOLUTION_REVIEW,
    AnnTypes.RESOLUTION,
    AnnTypes.ATTENDANCE_LIST,
    AnnTypes.ATTENDANT
]

all_annotations = []

line_ids_to_anchors = {}
line_ids_vs_occurrences = {}
resolution_annotations = []


def text_region_handler(text_region, begin_index, end_index, annotations, resource_id: str):
    # text_region['metadata'] contains enough info to construct annotations for page and scan.
    # this will result in duplicates, so deduplication at a later stage is necessary.

    if 'iiif_url' in text_region['metadata']:
        scan_annot_info = {
            'id': text_region['metadata']['scan_id'],
            'type': AnnTypes.SCAN.value,
            'resource_id': resource_id,
            'iiif_url': text_region['metadata']['iiif_url'],
            'begin_anchor': begin_index,
            'end_anchor': end_index
        }
        annotations.append(scan_annot_info)

        page_annot_info = {
            'id': text_region['metadata']['page_id'],
            'type': AnnTypes.PAGE.value,
            'resource_id': resource_id,
            'begin_anchor': begin_index,
            'end_anchor': end_index,
            'metadata': {
                'page_id': text_region['metadata']['page_id'],
                'scan_id': text_region['metadata']['scan_id']
            },
            'coords': text_region['coords']
        }
        annotations.append(page_annot_info)


untanngle_config = {
    AnnTypes.SESSION: {
        "child_key": "text_regions",
        "child_type": AnnTypes.TEXTREGION,
        "extra_fields": ["evidence"],
        "img_region_source": "text_regions"
    },
    AnnTypes.TEXTREGION: {
        "child_key": "lines",
        "child_type": AnnTypes.LINE,
        "extra_fields": ["coords"],
        "additional_processing": text_region_handler,
        "img_region_source": "present"
    },
    AnnTypes.LINE: {
        "child_key": None,
        "child_type": None,
        "extra_fields": ["baseline", "coords"],
        "img_region_source": "construct"
    },
    AnnTypes.RESOLUTION: {
        "child_key": "paragraphs",
        "child_type": AnnTypes.PARAGRAPH,
        "extra_fields": ["evidence"],
        "img_region_source": "line"
    },
    AnnTypes.PARAGRAPH: {
        "child_key": None,
        "child_type": None,
        "extra_fields": ["line_ranges", "text"],
        "img_region_source": "line"
    },
    AnnTypes.RESOLUTION_REVIEW: {
        "child_key": None,
        "child_type": None,
        "extra_fields": ["line_ranges", "text"],
        "img_region_source": "line"
    },
    AnnTypes.ATTENDANCE_LIST: {
        "child_key": "paragraphs",
        "child_type": AnnTypes.PARAGRAPH,
        "extra_fields": ["attendance_spans"],
        "img_region_source": "line"
    },
    AnnTypes.PAGE: {
        "extra_fields": ["coords"],
        "img_region_source": "merge_regions"
    },
    AnnTypes.ATTENDANT: {
        "img_region_source": "line"
    },
    AnnTypes.SCAN: {
        "img_region_source": "present"
    }
}


# We want to load 'text containers' that contain more or less contiguous text and are as long as practically
# possible. Container size is determined by pragmatic reasons, e.g. technical (performance) or user driven
# (corresponding with all scans in a book or volume). This functions returns all component files IN TEXT ORDER.
# Examples: sorted list of files, part of IIIF manifest.
def get_session_files(sessions_folder: str) -> List[str]:
    path = f"{sessions_folder}session-*-num*.json"
    session_file_names = (f for f in glob.glob(path))
    return sorted(session_file_names)


def sanity_check(node):
    if "metadata" in node and "iiif_url" in node["metadata"]:
        urls = node["metadata"]["iiif_url"]
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            if not image_id_pattern.search(url):
                logger.error(f"invalid iiif_url: {url}")


# Many file types contain a hierarchy of ordered text and/or annotation elements of different types. Some form of
# depth-first, post order traversal is necessary. Examples: processing a json hierarchy with dictionaries
# and lists (republic) or parsing TEI XML (DBNL document).
def traverse(node: Dict[str, Any], node_type: AnnTypes, text: IndexedSegmentedText, annotations, resource_id: str,
             provenance_source: str, line_anchor_idx: Dict[str, int]):
    # find the list that represents the children, each child is a dict
    config = untanngle_config[node_type]
    key_of_children = config['child_key']
    type_of_children = config['child_type']

    metadata = node['metadata'] if 'metadata' in node else None
    sanity_check(node)
    inventory_id = get_inventory_id(node)
    begin_index = text.len()
    annotation_info = {
        'id': node['id'],
        'type': node_type.value,
        'inventory_id': inventory_id,
        'resource_id': resource_id,
        'provenance_source': provenance_source,
        'begin_anchor': begin_index,
        'metadata': metadata,
    }

    # add selected extra_fields to annotation_info
    extra_fields = config['extra_fields']
    for f in extra_fields:
        annotation_info[f] = node[f]

    children = node[key_of_children] if key_of_children is not None else []
    if len(children) == 0:  # if no children, do your 'leaf node thing'
        annotation_info['end_anchor'] = text.len()
        node_text = node['text']

        if node_text is None:
            node_text = '\n'
        line_anchor = len(line_anchor_idx)
        line_anchor_idx[node['id']] = line_anchor
        text.append(node_text)
    else:  # if non-leaf node, first visit children
        for child in children:
            traverse(child, type_of_children, text, annotations, resource_id, provenance_source, line_anchor_idx)

        end_index = text.len() - 1
        annotation_info['end_anchor'] = end_index  # after child text segments are added

    annotations.append(annotation_info)

    if 'additional_processing' in config:
        config['additional_processing'](node, begin_index, end_index, annotations, resource_id)


# In case of presence of a hierarchical structure, processing/traversal typically starts from a root element.
def get_root_tree_element(file):
    with open(file, 'r') as myfile:
        session_file = myfile.read()

    session_data = json.loads(session_file)
    return session_data['_source']


# Rudimentary version of a scanpage_handler
def deduplicate_annotations(a_array, type):
    # filter annotation_info dicts of 'type'
    typed_annots = [ann_info for ann_info in a_array if ann_info['type'] == type.value]

    # use groupBy on a list of dicts (zie Python cookbook 1.15)
    from operator import itemgetter
    from itertools import groupby

    # first sort on scans' id
    typed_annots.sort(key=itemgetter('id'))

    # iterate in groups
    aggregated_typed_annots = []

    for _, items in groupby(typed_annots, key=itemgetter('id')):
        # first, convert the 'items' iterator to a list, to be able to use it twice (iterators can be used once)
        item_list = list(items)

        # copy the item with the lowest begin_index
        aggr_typed_annot = min(item_list, key=itemgetter('begin_anchor')).copy()

        # replace 'end_anchor' with the highest end_index in the group
        max_end_index = max(item_list, key=itemgetter('end_anchor'))['end_anchor']
        aggr_typed_annot['end_anchor'] = max_end_index

        # add to result
        aggregated_typed_annots.append(aggr_typed_annot)

    # replace old scan annotations with correct aggregated ones
    for old_annot in typed_annots:
        a_array.remove(old_annot)

    a_array.extend(aggregated_typed_annots)


def get_resolution_files(resolutions_folder: str):
    path = f'{resolutions_folder}session-*-resolutions.json'
    resolution_file_names = (f for f in glob.glob(path))
    return sorted(resolution_file_names)


def res_traverse(node, resource_id: str, provenance_source: str):
    # find the list that represents the children, each child is a dict, assume first list is the correct one
    types = node['type']
    # ignore 'reviewed'
    reviewed_type = 'reviewed'
    if reviewed_type in types:
        types.remove(reviewed_type)
    node_label = types[-1]
    config = untanngle_config[AnnTypes(node_label)]

    key_of_children = config['child_key']
    # type_of_children = config['child_type']

    children = [] if key_of_children is None else node[key_of_children]

    if len(children) == 0:  # if no children, do your 'leaf node thing'
        if len(node['line_ranges']) == 0:  # no associated lines, skip this node
            return
        else:
            begin_line_id = node['line_ranges'][0]['line_id']
            end_line_id = node['line_ranges'][-1]['line_id']

    else:  # if non-leaf node, first visit children
        relevant_children = [c for c in children if c['line_ranges']]
        begin_line_id = relevant_children[0]['line_ranges'][0]['line_id']
        end_line_id = relevant_children[-1]['line_ranges'][-1]['line_id']
        for child in relevant_children:
            res_traverse(child, resource_id, provenance_source)

    if 'additional_processing' in config:
        config['additional_processing'](node)

    inventory_id = get_inventory_id(node)

    annotation_info = {
        'id': node['id'],
        'type': node_label,
        'inventory_id': inventory_id,
        'resource_id': resource_id,
        'provenance_source': provenance_source,
        'begin_anchor': begin_line_id,
        'end_anchor': end_line_id,
        'metadata': node['metadata']
    }

    # add selected extra_fields to annotation_info
    extra_fields = config['extra_fields']
    for f in extra_fields:
        if AnnTypes(node_label) == AnnTypes.ATTENDANCE_LIST and node['attendance_spans'] == []:
            logging.warning(f"node {node['id']}: empty attendance_span")
        annotation_info[f] = node[f]

    resolution_annotations.append(annotation_info)


def get_inventory_id(node):
    if 'inventory_id' in node:
        inventory_id = node['inventory_id']
    elif 'metadata' in node and 'page_ids' in node['metadata']:
        page_id = node['metadata']['page_ids'][0]
        inventory_id = extract_inventory_id(page_id)
    elif 'metadata' in node and 'page_id' in node['metadata']:
        page_id = node['metadata']['page_id']
        inventory_id = extract_inventory_id(page_id)
    elif 'metadata' in node and 'scan_id' in node['metadata']:
        page_id = node['metadata']['page_id']
        inventory_id = extract_inventory_id(page_id)
    else:
        logging.error(f"no inventory_id for {node}")
        raise Exception(f"no inventory_id for {node}")
    return inventory_id


def extract_inventory_id(page_id):
    parts = page_id.split('_')
    inventory_id = "_".join(parts[:3])
    return inventory_id


# In case of presence of a hierarchical structure, processing/traversal typically starts from a root element.
def get_res_root_element(file):
    with open(file, 'r') as myfile:
        resolution_file = myfile.read()

    resolution_data = json.loads(resolution_file)
    return resolution_data['hits']['hits']


def collect_attendant_info(span, paras, paragraph_anchor: Dict[str, int]):
    result = None

    pattern = span['pattern'].strip()
    # ic(span['pattern'], span['offset'], span['end'], [(p['id'], p['text']) for p in paras])
    att_begin = span['offset']
    att_end = span['end']
    if att_begin < 0:
        logging.warning(f"span {span}: span['offset'] ({span['offset']}) < 0")
        return result

    if att_end < 0:
        logging.warning(f"span {span}: span['end'] ({span['end']}) < 0")
        return result

    char_ptr = 0
    last_end = 0
    line_ids_not_in_index = set()
    begin_anchor = 0
    begin_char_offset = 0
    start_paragraph_id = None
    relevant_paragraph_texts = []

    for p in paras:
        # ic(p['text'])
        if result is not None:  # bit ugly, to break out of both loops when result is reached
            break
        char_ptr += last_end

        for lr in p['line_ranges']:
            last_end = lr['end']
            line_begin = lr['start'] + char_ptr - 1
            line_end = lr['end'] + char_ptr

            if lr['line_id'] in line_ids_to_anchors:
                anchor = line_ids_to_anchors[lr['line_id']]
                # ic(anchor)
                # ic(line_begin, att_begin, line_end)
                if line_begin <= att_begin < line_end:
                    begin_anchor = anchor  # TODO: find out why begin_anchor == 0 for some attendants
                    begin_char_offset = att_begin - lr['start']
                    start_paragraph_id = p['id']
                # ic(start_paragraph_id)
                if start_paragraph_id:
                    relevant_paragraph_texts.append(p['text'])
                if line_begin <= att_end <= line_end:
                    end_anchor = anchor
                    end_char_offset = att_end - lr['start']
                    par_text = '\n'.join(relevant_paragraph_texts)

                    # p_start_offset = p['metadata']['start_offset'] - (
                    #             p['metadata']['paragraph_index'] * 2)  # because of double(?) space between paragraphs
                    # ic(par_text, pattern)
                    if pattern in par_text:
                        p_start_offset = par_text.index(pattern)
                    else:
                        p_start_offset = par_text.replace("\n", " ").index(pattern.replace("\n", " "))

                    if '\n' in pattern:
                        parts = pattern.split('\n')
                        p_end_offset = len(parts[-1])
                    else:
                        p_end_offset = p_start_offset + len(pattern)
                    result = {
                        'begin_anchor': begin_anchor,
                        'begin_char_offset': begin_char_offset,
                        'end_anchor': end_anchor,
                        'end_char_offset': end_char_offset,
                        'logical_begin_anchor': paragraph_anchor[start_paragraph_id],
                        'logical_end_anchor': paragraph_anchor[p['id']],
                        'logical_begin_char_offset': p_start_offset,
                        'logical_end_char_offset': p_end_offset
                    }
                    if result['logical_begin_anchor'] > result['logical_end_anchor']:
                        logging.error(
                            f"logical_begin_anchor ({result['logical_begin_anchor']}) > logical_end_anchor ({result['logical_end_anchor']})")
                    if (result['logical_begin_anchor'] == result['logical_end_anchor']) and (
                            result['logical_begin_char_offset'] >= result['logical_end_char_offset']):
                        logging.error(
                            f"logical_begin_char_offset ({result['logical_begin_char_offset']}) >="
                            f" logical_end_char_offset ({result['logical_end_char_offset']}) ")
                        logging.info(relevant_paragraph_texts)
                    logging.debug(
                        f"result! for: l_begin: {line_begin}, l_end: {line_end}, att_begin: {att_begin}, att_end: {att_end}")
                    break
                else:
                    logging.debug(
                        f"no result for: l_begin: {line_begin}, l_end: {line_end}, att_begin: {att_begin}, att_end: {att_end}")

            else:
                line_ids_not_in_index.add(lr['line_id'])
                logging.warning(f"span {span}: {lr['line_id']} not found in line_ids_vs_indexes")
        char_ptr += 1  # paragraphs are concatenated with space in between
    if line_ids_not_in_index:
        logging.warning(f"span {span}: {len(line_ids_not_in_index)} `line_id`s missing from line_ids_vs_indexes")
    return result


def create_attendants_for_attlist(attlist, session_id, resource_id, provenance_source: str,
                                  paragraph_anchor: Dict[str, int]):
    attendant_annots = []

    spans = attlist['attendance_spans']

    # sess = asearch.get_annotation_by_id(session_id, all_annotations)
    paras = list(asearch.get_annotations_of_type_overlapping('republic_paragraph',
                                                             attlist['begin_anchor'],
                                                             attlist['end_anchor'],
                                                             all_annotations,
                                                             resource_id))
    logging.debug(f"{len(paras)} republic_paragraphs found")
    for index, span in enumerate(spans):
        if span['class'] in attendant_classes:
            attendant = {
                'id': f'{session_id}-attendant-{index}',
                'type': 'attendant',
                'resource_id': resource_id,
                'provenance_source': provenance_source,
                'metadata': span
            }

            a_info = collect_attendant_info(span, paras, paragraph_anchor)
            if a_info is None:  # span not matching with text of paras
                logging.error(f"span {span}: does not match for session {session_id}")
            else:
                for key in ['begin_anchor', 'begin_char_offset',
                            'end_anchor', 'end_char_offset',
                            'logical_begin_anchor', 'logical_begin_char_offset',
                            'logical_end_anchor', 'logical_end_char_offset']:
                    attendant[key] = a_info[key]

                # TODO: this is a band-aid solution for attendant annotations with too many targets; fix it earlier!
                if attendant['begin_anchor'] == 0:
                    logger.warning(f"attendant['begin_anchor'] == 0 for {attendant['id']}")
                    attendant['begin_anchor'] = attendant['end_anchor']

                attendant_annots.append(attendant)

    return attendant_annots


# assume that iiif_urls refer to the same image resource
def union_of_iiif_urls(urls):
    # check if urls contain same image_identifier
    img_id = image_id_pattern.search(urls[0]).group(2)

    # Initialize the bounding region coordinates
    min_left, max_right, min_top, max_bottom = float('inf'), float('-inf'), float('inf'), float('-inf')

    # for each url, find left, right, top, bottom
    for url in urls:
        if not image_id_pattern.search(url):
            logging.error(f"{url} doesn't match expected pattern, skipping")
        else:
            if image_id_pattern.search(url).group(2) != img_id:
                # print(f'\t{urls[0]}')
                logging.error(f"{url} refers to other image than {img_id}")
                break

            region_string = region_pattern.search(url)
            left, top, width, height = map(int, region_string.groups()[1:5])
            right = left + width
            bottom = top + height

            # Update the bounding region coordinates
            min_left = min(min_left, left)
            max_right = max(max_right, right)
            min_top = min(min_top, top)
            max_bottom = max(max_bottom, bottom)

    height = max_bottom - min_top
    width = max_right - min_left

    # Construct the IIIF URL by replacing the coordinate part in the first input URL
    bounding_region_str = f"{min_left},{min_top},{width},{height}"
    bounding_url = re.sub(r'\d+,\d+,\d+,\d+', bounding_region_str, urls[0])

    return bounding_url


def get_bounding_box_for_coords(coords):
    min_left = min([crd[0] for crd in coords])
    max_right = max([crd[0] for crd in coords])
    min_top = min([crd[1] for crd in coords])
    max_bottom = max([crd[1] for crd in coords])
    if str(min_left) == "inf":
        logger.error(f"bounding box failure for {coords}")

    return {
        'left': min_left,
        'top': min_top,
        'right': max_right,
        'bottom': max_bottom,
        'width': max_right - min_left,
        'height': max_bottom - min_top
    }


def store_segmented_text(segmented_text: IndexedSegmentedText, store_path: str):
    data = segmented_text.__dict__
    data.pop("text_grid_spec")

    logging.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='UTF8') as filehandle:
        json.dump(data, filehandle, indent=4, cls=segmentedtext.SegmentEncoder, ensure_ascii=False)


def store_paragraph_text(paragraphs: List[str], store_path: str):
    data = {"_ordered_segments": paragraphs}
    logging.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='UTF8') as filehandle:
        json.dump(data, filehandle, indent=4, ensure_ascii=False)


def store_annotations(annotations, store_path: str):
    logging.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='UTF8') as filehandle:
        json.dump(annotations, filehandle, indent=4, cls=segmentedtext.AnchorEncoder, ensure_ascii=False)


def check_annotations(annotations):
    id_set = set()
    for a in annotations:
        a_id = a["id"]
        if a_id in id_set:
            logger.error(f"duplicate id: {a_id}, source: {a['provenance_source']}")
        else:
            id_set.add(a_id)


# maps line anchor to LogicalAnchorRange


def with_logical_anchors(annotation):
    if 'logical_begin_anchor' not in annotation:
        begin_logical_range = logical_anchor_range_for_line_anchor[annotation['begin_anchor']]
        annotation['logical_begin_anchor'] = begin_logical_range.begin_logical_anchor
        annotation['logical_begin_char_offset'] = begin_logical_range.begin_char_offset

        end_logical_range = logical_anchor_range_for_line_anchor[annotation['end_anchor']]
        annotation['logical_end_anchor'] = end_logical_range.end_logical_anchor
        annotation['logical_end_char_offset'] = end_logical_range.end_char_offset

        if begin_logical_range.begin_logical_anchor > end_logical_range.end_logical_anchor:
            logging.warn(
                f"begin_logical_range.begin_logical_anchor ({begin_logical_range.begin_logical_anchor}) >"
                f" end_logical_range.end_logical_anchor ({end_logical_range.end_logical_anchor}) for {annotation['id']},"
                f" swapping"
            )
            annotation['logical_begin_anchor'], annotation['logical_end_anchor'] = \
                annotation['logical_end_anchor'], annotation['logical_begin_anchor']
            annotation['logical_begin_char_offset'] = end_logical_range.begin_char_offset
            annotation['logical_end_char_offset'] = begin_logical_range.end_char_offset
            # else:
        #     logging.info(f"logical range is valid for {annotation['id']}")
    return annotation


def add_logical_anchors(annotations):
    return [with_logical_anchors(a) for a in annotations]


def untanngle_year(year: int, data_dir: str):
    datadir = f"{data_dir}/{year}"
    logfile = f'{datadir}/untanngle-republic-{year}.log'
    logger.info(f"logging to {logfile}")
    logging.basicConfig(filename=logfile,
                        encoding='utf-8',
                        filemode='w',
                        format='%(asctime)s | %(levelname)s | %(message)s',
                        level=logging.INFO)

    sessions_folder = f'sessions/'
    resolutions_folder = f'resolutions/'
    text_store = f'textstore-{year}.json'
    annotation_store = f'annotationstore-{year}.json'
    resource_id = f'volume-{year}'

    all_textlines, line_anchor_idx = traverse_session_files(f'{datadir}/{sessions_folder}', resource_id)
    store_segmented_text(all_textlines, f'{datadir}/{text_store}')

    deduplicate_annotations(all_annotations, AnnTypes.SCAN)
    logging.info(f"after removing duplicate scan annotations: {len(all_annotations)} annotations")

    deduplicate_annotations(all_annotations, AnnTypes.PAGE)
    logging.info(f"after removing duplicate page annotations: {len(all_annotations)} annotations")

    logging.info(f"traverse_resolution_files({resolutions_folder},{resource_id})")
    traverse_resolution_files(f'{datadir}/{resolutions_folder}', resource_id)

    logging.info(f"index_line_annotations({resource_id})")
    index_line_annotations(resource_id)

    logging.info("sanity_check_line_id_occurrences()")
    sanity_check_line_id_occurrences()

    logging.info("set_anchors_in_resolution_annotations()")
    set_anchors_in_resolution_annotations()

    logging.info(f"check_for_missing_attendance_lists_in_session_annotations({resource_id})")
    check_for_missing_attendance_lists_in_session_annotations(resource_id)

    paragraph_anchor_idx = extract_paragraph_text(datadir, year, line_anchor_idx)

    logging.info(f"add_attendant_annotations({resource_id})")
    add_attendant_annotations(resource_id, paragraph_anchor_idx)

    check_annotations(all_annotations)

    logging.info(f"add_region_links_to_page_annotations({resource_id})")
    add_region_links_to_page_annotations(resource_id)

    logging.info(f"add_region_links_to_session_annotations({resource_id})")
    add_region_links_to_session_annotations(resource_id)

    logging.info(f"add_region_links_to_line_annotations({resource_id})")
    add_region_links_to_line_annotations(resource_id)

    # with open(f"{datadir}/ut_annotations.json", "w") as f:
    #     json.dump(all_annotations, f, indent=2)
    logging.info(f"process_line_based_types()")
    process_line_based_types()

    logging.info(f"add_region_links_to_text_region_annotations({resource_id})")
    add_region_links_to_text_region_annotations(resource_id)

    logging.info(f"fix_scan_annotations({resource_id})")
    fix_scan_annotations(resource_id)

    logging.info(f"add_logical_anchors()")
    _annotations = add_logical_anchors(all_annotations)

    # logging.info("add_provenance()")
    # add_provenance()

    store_annotations(_annotations, f'{datadir}/{annotation_store}')


def extract_paragraph_text(datadir, year, line_anchor_idx) -> Dict[str, int]:
    paragraph_anchor_idx = {}
    logical_text_store = f'logical-textstore-{year}.json'
    all_paragraph_texts = []
    paragraph_annotations = [a for a in all_annotations if
                             a['type'] in [AnnTypes.RESOLUTION_REVIEW.value, AnnTypes.PARAGRAPH.value]]
    for pa in sorted(paragraph_annotations, key=lambda a: line_anchor_idx[a['line_ranges'][0]['line_id']]):
        anchor = len(all_paragraph_texts)
        paragraph_anchor_idx[pa['id']] = anchor
        pa['logical_begin_anchor'] = anchor
        pa['logical_end_anchor'] = anchor
        all_paragraph_texts.append(pa['text'])
        for line_range in pa['line_ranges']:
            line_anchor = line_ids_to_anchors[line_range['line_id']]
            start = line_range['start']
            end = line_range['end']
            logical_anchor_range_for_line_anchor[line_anchor] = LogicalAnchorRange(
                begin_logical_anchor=anchor, begin_char_offset=start, end_logical_anchor=anchor, end_char_offset=end
            )
    store_paragraph_text(all_paragraph_texts, f'{datadir}/{logical_text_store}')
    return paragraph_anchor_idx


def traverse_session_files(sessions_folder, resource_id) -> (IndexedSegmentedText, dict[str, Any]):
    line_anchor_idx = {}
    all_textlines = segmentedtext.IndexedSegmentedText(resource_id)
    # Process per file, properly concatenate results, maintaining proper referencing the baseline text elements
    for f_name in get_session_files(sessions_folder):
        logging.info(f"<= {f_name}")

        source_data = get_root_tree_element(f_name)
        text_array = segmentedtext.IndexedSegmentedText()
        annotation_array = []
        provenance_source = f"{session_es_index}/_doc/{source_data['id']}"

        traverse(source_data, AnnTypes.SESSION, text_array, annotation_array, resource_id, provenance_source,
                 line_anchor_idx)

        # properly concatenate annotation info taking ongoing line indexes into account
        for ai in annotation_array:
            ai['begin_anchor'] += all_textlines.len()
            ai['end_anchor'] += all_textlines.len()

        all_textlines.extend(text_array)
        all_annotations.extend(annotation_array)
    logging.info(f"{len(all_annotations)} annotations")
    return all_textlines, line_anchor_idx


def traverse_resolution_files(resolutions_folder, resource_id):
    for f_name in get_resolution_files(resolutions_folder):
        # get list of resolution 'hits'
        hits = get_res_root_element(f_name)
        for hit in hits:
            # each hit corresponds with a resolution
            resolution = hit['_source']
            res_traverse(resolution, resource_id,
                         f"{resolution_es_index}/_doc/{resolution['id']}", )


def sanity_check_line_id_occurrences():
    for k in line_ids_vs_occurrences:
        if line_ids_vs_occurrences[k] > 2:
            logging.info(f"id: {k} occurs {line_ids_vs_occurrences[k]} times")


def index_line_annotations(resource_id):
    # for line in all_annotations:
    for line in asearch.get_annotations_of_type('line', all_annotations, resource_id):
        #    if line['type'] == 'line':
        line_ids_to_anchors.update({line['id']: line['begin_anchor']})
        if line['id'] not in line_ids_vs_occurrences:
            line_ids_vs_occurrences[line['id']] = 1
        else:
            line_ids_vs_occurrences[line['id']] += 1


def set_anchors_in_resolution_annotations():
    num_errors = 0
    for res in resolution_annotations:
        if res['begin_anchor'] in line_ids_to_anchors:
            res['begin_anchor'] = line_ids_to_anchors[res['begin_anchor']]
        else:
            logging.error(f"missing line annotation {res['begin_anchor']}")
            res["begin_anchor"] = 0
            num_errors += 1
        if res['end_anchor'] in line_ids_to_anchors:
            res['end_anchor'] = line_ids_to_anchors[res['end_anchor']]
        else:
            logging.error(f"missing line annotation {res['end_anchor']}")
            res['end_anchor'] = 0
            num_errors += 1

    if num_errors > 0:
        logging.error(f"number of lookup errors for line_indexes vs line_ids: {num_errors}")
    all_annotations.extend(resolution_annotations)


def check_for_missing_attendance_lists_in_session_annotations(resource_id):
    # blijkbaar komen er sessies voor zonder attendance_list. Check dit even
    for sess in asearch.get_annotations_of_type('session', all_annotations, resource_id):
        alists = list(asearch.get_annotations_of_type_overlapping('attendance_list',
                                                                  sess['begin_anchor'], sess['end_anchor'],
                                                                  all_annotations,
                                                                  resource_id))
        if len(alists) == 0:
            logging.warning(f"session {sess['id']} has no attendance_list")


def add_attendant_annotations(resource_id: str, paragraph_anchor: Dict[str, int]):
    attendant_annotations = []
    for al in asearch.get_annotations_of_type('attendance_list', all_annotations, resource_id):
        session_id = al['metadata']['session_id']
        atts = create_attendants_for_attlist(al, session_id, resource_id, al['provenance_source'], paragraph_anchor)
        attendant_annotations.extend(atts)
        # set_logical_text_offset(al, atts)

    all_annotations.extend(attendant_annotations)


def set_logical_text_offset(al, atts):
    min_logical_position = (sys.maxsize, sys.maxsize)
    max_logical_position = (0, 0)
    for att in atts:
        if (att['logical_begin_anchor'] < min_logical_position[0] or
                (att['logical_begin_anchor'] == min_logical_position[0] and
                 att['logical_begin_char_offset'] < min_logical_position[1])):
            min_logical_position = (att['logical_begin_anchor'], att['logical_begin_char_offset'])
        if (att['logical_end_anchor'] > max_logical_position[0] or
                (att['logical_end_anchor'] == max_logical_position[0] and
                 att['logical_end_char_offset'] > max_logical_position[1])):
            max_logical_position = (att['logical_end_anchor'], att['logical_end_char_offset'])
    al['logical_begin_anchor'] = min_logical_position[0]
    al['logical_begin_char_offset'] = min_logical_position[1]
    al['logical_end_anchor'] = max_logical_position[0]
    al['logical_end_char_offset'] = max_logical_position[1]
    if al['logical_begin_anchor'] > al['logical_end_anchor']:
        logging.error(
            f"logical_begin_anchor ({al['logical_begin_anchor']}) > logical_end_anchor ({al['logical_end_anchor']})")


def add_region_links_to_page_annotations(resource_id):
    # vraag alle page annotations op
    pg_annots = list(asearch.get_annotations_of_type('page', all_annotations, resource_id))
    with alive_bar(len(pg_annots), title="Processing page annotations", spinner=None) as bar:
        for pa in pg_annots:
            pa['region_links'] = calculate_region_links_for_page_annotation(pa, resource_id)
            bar()


def calculate_region_links_for_page_annotation(pa, resource_id):
    # per page, vraag alle overlappende text_regions op
    overlapping_regions = list(
        asearch.get_annotations_of_type_overlapping(
            'text_region',
            pa['begin_anchor'], pa['end_anchor'],
            all_annotations, resource_id
        )
    )
    # verzamel alle iiif_urls daarvan en unificeer die
    urls = [tr['metadata']['iiif_url'] for tr in overlapping_regions]
    bounding_url = union_of_iiif_urls(urls)
    return [bounding_url]


def add_region_links_to_session_annotations(resource_id):
    # vraag alle sessions op
    s_annots = list(asearch.get_annotations_of_type('session', all_annotations, resource_id))
    with alive_bar(len(s_annots), title="Processing session annotations", spinner=None) as bar:
        for s in s_annots:
            s['region_links'] = calculate_region_links_for_session_annotation(resource_id, s)
            bar()


def calculate_region_links_for_session_annotation(resource_id, s):
    # per session, vraag alle text_regions op
    overlapping_regions = list(asearch.get_annotations_of_type_overlapping('text_region',
                                                                           s['begin_anchor'], s['end_anchor'],
                                                                           all_annotations, resource_id))
    # verzamel alle iiif_urls daarvan en zet ze in volgorde in 'region_links'
    overlapping_regions.sort(key=lambda r_ann: r_ann['begin_anchor'])
    urls = [tr['metadata']['iiif_url'] for tr in overlapping_regions]
    return urls


def add_region_links_to_line_annotations(resource_id):
    # vraag alle lines op
    line_annots = list(asearch.get_annotations_of_type('line', all_annotations, resource_id))
    with alive_bar(len(line_annots), title="Processing line annotations", spinner=None) as bar:
        # voeg iiif region_links toe aan alle line annotaties
        for line in line_annots:
            line['region_links'] = calculate_region_links_for_line_annotation(line)
            bar()


def calculate_region_links_for_line_annotation(line):
    coords = line['coords']
    bb = get_bounding_box_for_coords(coords)
    bb_str = f"{bb['left']},{bb['top']},{bb['width']},{bb['height']}"
    scan_id = line['metadata']['scan_id']
    items = scan_id.split('_')
    region_url = f"{iiif_base}{items[0]}_{items[1]}/{items[2]}/{scan_id}.jpg/{bb_str}{iiif_extension}"
    return [region_url]


def process_line_based_types():
    types = {at.value for at in line_based_types}
    relevant_annotations = [a for a in all_annotations if a['type'] in types]
    text_region_annotations = [a for a in all_annotations if a['type'] == 'text_region']
    text_region_annotation_wrapper = AnnotationsWrapper(text_region_annotations)
    line_annotations = [a for a in all_annotations if a['type'] == 'line']
    line_annotation_wrapper = AnnotationsWrapper(line_annotations)
    with alive_bar(len(relevant_annotations), title="Processing line-based annotations", spinner=None) as bar:
        for annotation in relevant_annotations:
            annotation['region_links'] = calculate_region_links(
                annotation,
                line_annotation_wrapper,
                text_region_annotation_wrapper
            )
            bar()


def calculate_region_links(ann, line_annotation_wrapper, text_region_annotation_wrapper):
    ann_region_links = []
    # voor iedere resolutie, vraag overlappende regions
    begin_anchor = ann['begin_anchor']
    end_anchor = ann['end_anchor']
    with_anchor_range = text_region_annotation_wrapper.get_annotations_overlapping_with_anchor_range(begin_anchor,
                                                                                                     end_anchor)
    overlapping_regions = sorted(
        with_anchor_range,
        key=lambda reg_ann: reg_ann['begin_anchor']
    )
    lines_in_annotation = line_annotation_wrapper.get_annotations_overlapping_with_anchor_range(begin_anchor,
                                                                                                end_anchor)
    # bepaal bounding box voor met RESOLUTION overlappende lines, per text_region
    for tr in overlapping_regions:
        line_ids_in_region = {
            a["id"] for a in
            line_annotation_wrapper.get_annotations_overlapping_with_anchor_range(tr['begin_anchor'], tr['end_anchor'])
        }
        lines_in_intersection = (line_a for line_a in lines_in_annotation if line_a["id"] in line_ids_in_region)

        # determine iiif url region enclosing the line boxes, assume each line has only one url
        urls = [line['region_links'][0] for line in lines_in_intersection]
        if not urls:
            logger.error(f"no urls found for {tr['id']} {tr['begin_anchor']}:{tr['end_anchor']}")
            logger.info(f"line_ids_in_region={lines_in_intersection}")
        else:
            region_url = union_of_iiif_urls(urls)
            ann_region_links.append(region_url)

        # # generate output to report potential issues with layout of text_regions
        # region_string = region_pattern.search(region_url)
        # width = int(region_string.group(4))
        # if width > 2000:
        #     logging.warning(
        #         f"annotation {ann}: potential error in layout, width of text_region {tr['id']} too large: {width}")
    return ann_region_links


def process_line_based_types0(resource_id):
    for ann_type in line_based_types:
        annots = asearch.get_annotations_of_type(ann_type.value, all_annotations, resource_id)
        logging.info(f"Processing annotation type {ann_type}")
        for num, ann in enumerate(annots):
            ann_region_links = []

            # voor iedere resolutie, vraag overlappende regions
            overlapping_regions = sorted(
                asearch.get_annotations_of_type_overlapping(
                    'text_region',
                    ann['begin_anchor'],
                    ann['end_anchor'],
                    all_annotations,
                    resource_id
                ),
                key=lambda reg_ann: reg_ann['begin_anchor']
            )

            lines_in_annotation = list(
                asearch.get_annotations_of_type_overlapping(
                    'line',
                    ann['begin_anchor'],
                    ann['end_anchor'],
                    all_annotations,
                    resource_id
                )
            )

            # bepaal bounding box voor met RESOLUTION overlappende lines, per text_region
            for tr in overlapping_regions:
                line_ids_in_region = set(
                    [a["id"] for a in asearch.get_annotations_of_type_overlapping(
                        'line',
                        tr['begin_anchor'],
                        tr['end_anchor'],
                        all_annotations,
                        resource_id
                    )]
                )

                lines_in_intersection = [line for line in lines_in_annotation if line["id"] in line_ids_in_region]

                # determine iiif url region enclosing the line boxes, assume each line has only one url
                urls = [line['region_links'][0] for line in lines_in_intersection]
                region_url = union_of_iiif_urls(urls)
                ann_region_links.append(region_url)

                # generate output to report potential issues with layout of text_regions
                region_string = region_pattern.search(region_url)
                width = int(region_string.group(4))
                if width > 2000:
                    logging.warning(
                        f"annotation {ann}: potential error in layout, width of text_region {tr['id']} too large: {width}")
                ann['region_links'] = ann_region_links


def add_region_links_to_text_region_annotations(resource_id):
    region_annots = list(asearch.get_annotations_of_type('text_region', all_annotations, resource_id))
    for ra in region_annots:
        ra['region_links'] = [ra['metadata']['iiif_url']]


def fix_scan_annotations(resource_id):
    scan_annots = list(asearch.get_annotations_of_type('scan', all_annotations, resource_id))
    for sa in scan_annots:
        sa['iiif_url'] = re.sub(r"(\d+),(\d+),(\d+),(\d+)/(max)", r'\5/,\4', sa['iiif_url'])
        sa['region_links'] = [sa['iiif_url']]


# def add_provenance():
#     for a in all_annotations:
#         a["provenance"] = provenance_data
#         if "metadata" in a and "index_timestamp" in a["metadata"]:
#             # logging.debug(a["id"])
#             a["provenance"]["index_timestamp"] = a["metadata"]["index_timestamp"]


@logger.catch
def main():
    tic = time.perf_counter()
    parser = argparse.ArgumentParser(
        description="Untanngle the harvested CAF data for the given year(s)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("year",
                        help="The year(s) to untanngle",
                        nargs='+',
                        type=int)
    parser.add_argument("-d", "--data-dir",
                        help="The directory where to find the downloaded CAS files",
                        required=True,
                        type=str)

    args = parser.parse_args()
    years = args.year
    data_dir = args.data_dir
    for year in sorted(years):
        untanngle_year(year, data_dir)
    logging.info("done!")
    toc = time.perf_counter()
    duration = str(datetime.timedelta(seconds=(toc - tic)))
    logger.info(f"processing took {duration}")


if __name__ == '__main__':
    main()
