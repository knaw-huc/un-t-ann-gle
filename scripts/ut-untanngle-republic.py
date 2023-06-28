#!/usr/bin/env python3
import argparse
import datetime
import glob
import json
import logging
import re
import time
import uuid
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
image_id_pattern = re.compile(r'(images.diginfra.net/iiif/)(.*)(\/)(\d+),(\d+),(\d+),(\d+)')
iiif_base = 'https://images.diginfra.net/iiif/'
iiif_extension = '/full/0/default.jpg'

resolution_es_index = "https://annotation.republic-caf.diginfra.org/elasticsearch/full_resolutions"
session_es_index = "https://annotation.republic-caf.diginfra.org/elasticsearch/session_lines"


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

# provenance_data = {
#     "source": "CAF 'session_lines' and 'resolutions' indexes",
#     "target": "json text array plus standoff annotation info in custom untanngle json format",
#     "harvesting_date": datetime.date.today(),
#     "conversion_date": datetime.date.today(),
#     "tool_id": "untanngle dd 15 maart 2023",
#     "motivation": "input for TextRepo and AnnoRepo, test in how far scripts work"
# }

all_annotations = []

line_ids_to_anchors = {}
line_ids_vs_occurrences = {}
resolution_annotations = []


def text_region_handler(node, begin_index, end_index, annotations, resource_id: str):
    # text_region['metadata'] contains enough info to construct annotations for page and scan.
    # this will result in duplicates, so deduplication at a later stage is necessary.

    if 'iiif_url' in node['metadata']:
        scan_annot_info = {
            'resource_id': resource_id,
            'type': AnnTypes.SCAN.value,
            'iiif_url': node['metadata']['iiif_url'],
            'begin_anchor': begin_index,
            'end_anchor': end_index,
            'id': node['metadata']['scan_id']
        }
        annotations.append(scan_annot_info)

        page_annot_info = {
            'resource_id': resource_id,
            'type': AnnTypes.PAGE.value,
            'begin_anchor': begin_index,
            'end_anchor': end_index,
            'id': node['metadata']['page_id'],
            'metadata': {
                'page_id': node['metadata']['page_id'],
                'scan_id': node['metadata']['scan_id']
            },
            'coords': node['coords']
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
             provenance_source: str):
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

        text.append(node_text)
    else:  # if non-leaf node, first visit children
        for child in children:
            traverse(child, type_of_children, text, annotations, resource_id, provenance_source)

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
    node_label = node['type'][-1]
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
        begin_line_id = children[0]['line_ranges'][0]['line_id']
        end_line_id = children[-1]['line_ranges'][-1]['line_id']
        for child in children:
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


def collect_attendant_info(span, paras):
    result = None

    att_begin = span['offset']
    att_end = span['end']
    if att_begin < 0:
        logging.warning(f"span {span}: span['offset'] ({span['offset']}) < 0")
        return result

    if att_end < 0:
        logging.warning(f"span {span}: span['end] ({span['end']}) < 0")
        return result

    char_ptr = 0
    last_end = 0
    line_ids_not_in_index = set()
    begin_anchor = 0
    begin_char_offset = 0

    for p in paras:
        if result is not None:  # bit ugly, to break out of both loops when result is reached
            break
        char_ptr += last_end

        for lr in p['line_ranges']:
            last_end = lr['end']
            line_begin = lr['start'] + char_ptr
            line_end = lr['end'] + char_ptr

            if lr['line_id'] in line_ids_to_anchors:
                anchor = line_ids_to_anchors[lr['line_id']]
                if line_begin <= att_begin < line_end:
                    begin_anchor = anchor
                    begin_char_offset = att_begin - lr['start']
                if line_begin <= att_end <= line_end:
                    end_anchor = anchor
                    end_char_offset = att_end - lr['start']

                    result = {
                        'begin_anchor': begin_anchor,
                        'end_anchor': end_anchor,
                        'begin_char_offset': begin_char_offset,
                        'end_char_offset': end_char_offset
                    }
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


def create_attendants_for_attlist(attlist, session_id, resource_id):
    attendant_annots = []

    spans = attlist['attendance_spans']

    # sess = asearch.get_annotation_by_id(session_id, all_annotations)
    paras = list(asearch.get_annotations_of_type_overlapping('republic_paragraph',
                                                             attlist['begin_anchor'],
                                                             attlist['end_anchor'],
                                                             all_annotations,
                                                             resource_id))
    logging.debug(f"{len(paras)} republic_parargraphs found")
    for index, span in enumerate(spans):
        if span['class'] in attendant_classes:
            attendant = {
                'resource_id': resource_id,
                'type': 'attendant',
                'id': f'{session_id}-attendant-{index}',
                'metadata': span
            }

            a_info = collect_attendant_info(span, paras)
            if a_info is None:  # span not matching with text of paras
                logging.error(f"span {span}: does not match for session {session_id}")
            else:
                attendant['begin_anchor'] = a_info['begin_anchor']
                attendant['end_anchor'] = a_info['end_anchor']
                attendant['begin_char_offset'] = a_info['begin_char_offset']
                attendant['end_char_offset'] = a_info['end_char_offset']

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
        if not image_id_pattern.match(url):
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


def store_annotations(annotations, store_path: str):
    logging.info(f"=> {store_path}")
    with open(store_path, 'w', encoding='UTF8') as filehandle:
        json.dump(annotations, filehandle, indent=4, cls=segmentedtext.AnchorEncoder, ensure_ascii=False)


def check_annotations(annotations):
    id_set = set()
    for a in annotations:
        a_id=a["id"]
        if a_id in id_set:
            logger.error(f"duplicate id: {a_id}")
        else:
            id_set.add(a_id)


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

    all_textlines = traverse_session_files(f'{datadir}/{sessions_folder}', resource_id)
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

    logging.info(f"add_attendant_annotations({resource_id})")
    add_attendant_annotations(resource_id)

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

    # logging.info("add_provenance()")
    # add_provenance()

    check_annotations(all_annotations)

    store_annotations(all_annotations, f'{datadir}/{annotation_store}')


def traverse_session_files(sessions_folder, resource_id):
    all_textlines = segmentedtext.IndexedSegmentedText(resource_id)
    # Process per file, properly concatenate results, maintaining proper referencing the baseline text elements
    for f_name in get_session_files(sessions_folder):
        logging.info(f"<= {f_name}")

        source_data = get_root_tree_element(f_name)
        text_array = segmentedtext.IndexedSegmentedText()
        annotation_array = []
        provenance_source = f"{session_es_index}/_doc/{source_data['id']}"

        traverse(source_data, AnnTypes.SESSION, text_array, annotation_array, resource_id, provenance_source)

        # properly concatenate annotation info taking ongoing line indexes into account
        for ai in annotation_array:
            ai['begin_anchor'] += all_textlines.len()
            ai['end_anchor'] += all_textlines.len()

        all_textlines.extend(text_array)
        all_annotations.extend(annotation_array)
    logging.info(f"{len(all_annotations)} annotations")
    return all_textlines


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


def add_attendant_annotations(resource_id):
    attendant_annotations = []
    for al in asearch.get_annotations_of_type('attendance_list', all_annotations, resource_id):
        session_id = al['metadata']['session_id']
        logging.info(session_id)
        atts = create_attendants_for_attlist(al, session_id, resource_id)
        attendant_annotations.extend(atts)
    all_annotations.extend(attendant_annotations)


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


class AnnotationsWrapper:
    def __init__(self, annotations: List):
        self.annotations = annotations
        self.annotation_idx = {a["id"]: a for a in annotations}
        max_anchor = max([a['end_anchor'] for a in annotations]) + 1
        store = AnnotationStore(id=uuid.uuid4())
        resource = store.add_resource(id="dummy", text="*" * max_anchor)
        annotation_set = store.add_annotationset(id="type_set")
        annotation_set.add_key("type")
        for a in self.annotations:
            a_type = a['type']
            type_data = annotation_set.add_data(key="type", value=a_type)
            store.annotate(
                id=a['id'],
                target=Selector.textselector(resource, Offset.simple(a['begin_anchor'], a['end_anchor'] + 1)),
                data=type_data
            )
        store.set_filename("out/store.json")
        store.save()
        self.resource = resource

    @cache
    def get_annotations_overlapping_with_anchor_range(self, begin_anchor, end_anchor):
        selection = self.resource.textselection(Offset.simple(begin_anchor, end_anchor + 1))
        overlapping = [self.annotation_idx[a.id()] for a in
                       selection.find_annotations(TextSelectionOperator.overlaps())]
        exact = [self.annotation_idx[a.id()] for a in selection.annotations()]
        return overlapping + exact


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
        sa['iiif_url'] = re.sub(r"(\d+),(\d+),(\d+),(\d+)/(full)", r'\5/,\4', sa['iiif_url'])
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
