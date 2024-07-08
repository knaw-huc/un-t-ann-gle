# untanngle process

import glob
import json
import re
import sys

sys.path.append('../packages')

from textservice import segmentedtext
from annotation import asearch

# resource locations
# year to harvest
year = 1728
harvestdate = 230315

# where to store harvest from CAF sessions index
# sessions_dump_file = f'sessions-{year}-output-19aug22.json'

# datadir = '../../data/1728/18jul22/'
datadir = f'./output-{harvestdate}/'
sessions_folder = f'CAF-sessions-{year}/'
resolutions_folder = f'CAF-resolutions-{year}/'
text_store = f'{year}-textstore-{harvestdate}.json'
annotation_store = f'{year}-annotationstore-{harvestdate}.json'
resource_id = 'volume-{year}'

import logging

logging.basicConfig(filename=datadir + 'errors.log', encoding='utf-8', filemode='w', level=logging.DEBUG)

# selected classes that refer to persons
attendant_classes = ('president', 'delegate', 'raadpensionaris')

# constants used for compilation of iiif urls
region_pattern = re.compile(r'(.jpg/)(\d+),(\d+),(\d+),(\d+)')
image_id_pattern = re.compile(r'(images.diginfra.net/iiif/)(.*)(\/)(\d+),(\d+),(\d+),(\d+)')
iiif_base = 'https://images.diginfra.net/iiif/'
iiif_extension = '/max/0/default.jpg'

from enum import Enum


class AnnTypes(Enum):
    SESSION = "session"
    TEXTREGION = "text_region"
    LINE = "line"
    RESOLUTION = "resolution"
    PARAGRAPH = "republic_paragraph"
    RESOLUTIONREVIEW = "reviewed"
    ATTENDANCELIST = "attendance_list"
    PAGE = "page"
    ATTENDANT = "attendant"
    SCAN = "scan"


line_based_types = [AnnTypes.SESSION, AnnTypes.PARAGRAPH, AnnTypes.RESOLUTIONREVIEW, AnnTypes.RESOLUTION, \
                    AnnTypes.ATTENDANCELIST, AnnTypes.ATTENDANT]

provenance_data = {
    "source": "CAF 'session_lines' and 'resolutions' indexes",
    "target": "json text array plus standoff annotation info in custom untanngle json format",
    "harvesting_date": "2023-03-15",
    "conversion_date": "2023-03-15",
    "tool_id": "untanngle dd 15 maart 2023",
    "motivation": "input for TextRepo and AnnoRepo, test in how far scripts work"
}


def text_region_handler(node, begin_index, end_index, annotations):
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

    return


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
    AnnTypes.RESOLUTIONREVIEW: {
        "child_key": None,
        "child_type": None,
        "extra_fields": ["line_ranges", "text"],
        "img_region_source": "line"
    },
    AnnTypes.ATTENDANCELIST: {
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

all_textlines = segmentedtext.IndexedSegmentedText(resource_id)
all_annotations = []


# We want to load 'text containers' that contain more or less contiguous text and are as long as practically
# possible. Container size is determined by pragmatic reasons, e.g. technical (performance) or user driven
# (corresponding with all scans in a book or volume). This functions returns all component files IN TEXT ORDER.
# Examples: sorted list of files, part of IIIF manifest.

def get_file_sequence_for_container(text_container):
    path = datadir + sessions_folder + "session-*-num*.json"
    session_file_names = (f for f in glob.glob(path))

    return sorted(session_file_names)


# Many file types contain a hierarchy of ordered text and/or annotation elements of different types. Some form of
# depth-first, post order traversal is necessary. Examples: processing a json hierarchy with dictionaries
# and lists (republic) or parsing TEI XML (DBNL document).

def traverse(node, node_type, text, annotations):
    # find the list that represents the children, each child is a dict
    config = untanngle_config[node_type]
    key_of_children = config['child_key']
    type_of_children = config['child_type']

    metadata = None if not 'metadata' in node else node['metadata']

    begin_index = text.len()
    annotation_info = {'resource_id': resource_id, 'type': node_type.value, \
                       'metadata': metadata, 'id': node['id'], 'begin_anchor': begin_index}

    # add selected extra_fields to annotation_info
    extra_fields = config['extra_fields']
    for f in extra_fields:
        annotation_info[f] = node[f]

    children = [] if key_of_children == None else node[key_of_children]
    if len(children) == 0:  # if no children, do your 'leaf node thing'

        annotation_info['end_anchor'] = text.len()
        node_text = node['text']

        if node_text is None:
            node_text = '\n'

        text.append(node_text)
    else:  # if non-leaf node, first visit children
        for child in children:
            traverse(child, type_of_children, text, annotations)

        end_index = text.len() - 1
        annotation_info['end_anchor'] = end_index  # after child text segments are added

    annotations.append(annotation_info)

    if 'additional_processing' in config:
        config['additional_processing'](node, begin_index, end_index, annotations)

    return


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

    for id, items in groupby(typed_annots, key=itemgetter('id')):
        # first, convert the 'items' iterator to a list, to able to use it twice (iterators can be used once)
        itemlist = list(items)

        # copy the item with the lowest begin_index
        aggr_typed_annot = min(itemlist, key=itemgetter('begin_anchor')).copy()

        # replace 'end_anchor' with the highest end_index in the group
        max_end_index = max(itemlist, key=itemgetter('end_anchor'))['end_anchor']
        aggr_typed_annot['end_anchor'] = max_end_index

        # add to result
        aggregated_typed_annots.append(aggr_typed_annot)

    # replace old scan annotations with correct aggregated ones
    for old_annot in typed_annots:
        a_array.remove(old_annot)

    a_array.extend(aggregated_typed_annots)

    return


# Process per file, properly concatenate results, maintaining proper referencing the baseline text elements
for f_name in get_file_sequence_for_container(resource_id):
    text_array = segmentedtext.IndexedSegmentedText()
    annotation_array = []

    source_data = get_root_tree_element(f_name)

    traverse(source_data, AnnTypes.SESSION, text_array, annotation_array)

    # properly concatenate annotation info taking ongoing line indexes into account
    for ai in annotation_array:
        ai['begin_anchor'] += all_textlines.len()
        ai['end_anchor'] += all_textlines.len()

    all_textlines.extend(text_array)
    all_annotations.extend(annotation_array)

deduplicate_annotations(all_annotations, AnnTypes.SCAN)
deduplicate_annotations(all_annotations, AnnTypes.PAGE)

resolution_annotations = []


def get_resolution_files_for_container(text_container):
    path = datadir + resolutions_folder + 'session-*-resolutions.json'

    resolution_file_names = (f for f in glob.glob(path))
    return sorted(resolution_file_names)


def res_traverse(node):
    # find the list that represents the children, each child is a dict, assume first list is the correct one
    node_label = node['type'][-1]
    config = untanngle_config[AnnTypes(node_label)]

    key_of_children = config['child_key']
    type_of_children = config['child_type']

    children = [] if key_of_children == None else node[key_of_children]

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
            res_traverse(child)

    if 'additional_processing' in config:
        config['additional_processing'](node)

    annotation_info = {'resource_id': resource_id, 'type': node_label, \
                       'begin_anchor': begin_line_id, \
                       'end_anchor': end_line_id, \
                       'metadata': node['metadata'], \
                       'id': node['id']}

    # add selected extra_fields to annotation_info
    extra_fields = config['extra_fields']
    for f in extra_fields:
        if AnnTypes(node_label) == AnnTypes.ATTENDANCELIST and node['attendance_spans'] == []:
            logging.warning(f"empty attendance_span for {node['id']}")
        annotation_info[f] = node[f]

    resolution_annotations.append(annotation_info)

    return


# In case of presence of a hierarchical structure, processing/traversal typically starts from a root element.

def get_res_root_element(file):
    with open(file, 'r') as myfile:
        resolution_file = myfile.read()

    resolution_data = json.loads(resolution_file)
    return resolution_data['hits']['hits']


for f_name in get_resolution_files_for_container(resource_id):
    # get list of resolution 'hits'
    hits = get_res_root_element(f_name)
    for hit in hits:
        # each hit corresponds with a resolution
        resolution_line_ids = []
        res_traverse(hit['_source'])

line_ids_vs_indexes = {}
line_ids_vs_occurances = {}
# for line in all_annotations:
for line in asearch.get_annotations_of_type('line', all_annotations, resource_id):
    #    if line['type'] == 'line':
    line_ids_vs_indexes.update({line['id']: line['begin_anchor']})
    if line['id'] not in line_ids_vs_occurances:
        line_ids_vs_occurances[line['id']] = 1
    else:
        line_ids_vs_occurances[line['id']] += 1

for k in line_ids_vs_occurances:
    if line_ids_vs_occurances[k] > 2:
        print(f"id: {k} occurs {line_ids_vs_occurances[k]} times")

num_errors = 0
for res in resolution_annotations:
    try:
        res['begin_anchor'] = line_ids_vs_indexes[res['begin_anchor']]
        res['end_anchor'] = line_ids_vs_indexes[res['end_anchor']]
    except:
        print(res)
        quit()
        res['begin_anchor'] = 0
        res['end_anchor'] = 0
        num_errors += 1

if num_errors > 0:
    logging.warning(f"number of lookup errors for line_indexes vs line_ids: {num_errors}")
    print(f"number of lookup errors for line_indexes vs line_ids: {num_errors}")

all_annotations.extend(resolution_annotations)


def collect_attendant_info(span, paras):
    char_ptr = 0
    last_end = 0
    begin_anchor = ''
    end_anchor = ''
    result = None

    for p in paras:
        if (result != None):  # bit ugly, to break out of both loops when result is reached
            break
        char_ptr += last_end

        for lr in p['line_ranges']:
            last_end = lr['end']

            att_begin = span['offset']
            att_end = span['end']
            line_begin = lr['start'] + char_ptr
            line_end = lr['end'] + char_ptr

            if att_begin < 0 or att_end < 0:
                # logging.warning(f"span['offset'] < 0 or span['end] < 0")
                break

            # print(f"l_begin: {line_begin}, l_end: {line_end}, att_begin: {att_begin}, att_end: {att_end}")

            if att_begin >= line_begin and att_begin < line_end:
                begin_anchor = line_ids_vs_indexes[lr['line_id']]
                begin_char_offset = att_begin - lr['start']
            if att_end >= line_begin and att_end < line_end:
                end_anchor = line_ids_vs_indexes[lr['line_id']]
                end_char_offset = att_end - lr['start']

                result = {'begin_anchor': begin_anchor, \
                          'end_anchor': end_anchor, \
                          'begin_char_offset': begin_char_offset, \
                          'end_char_offset': end_char_offset}
                break
    return result


def create_attendants_for_attlist(attlist, session_id, resource_id):
    attendant_annots = []

    spans = attlist['attendance_spans']

    sess = asearch.get_annotation_by_id(session_id, all_annotations)
    paras = list(asearch.get_annotations_of_type_overlapping('republic_paragraph', \
                                                             attlist['begin_anchor'], attlist['end_anchor'],
                                                             all_annotations, resource_id))

    for index, s in enumerate(spans):
        if s['class'] in attendant_classes:
            attendant = {'resource_id': resource_id, 'type': 'attendant'}
            attendant['id'] = session_id + '-attendant-' + str(index)
            attendant['metadata'] = s

            a_info = collect_attendant_info(s, paras)
            if a_info == None:  # span not matching with text of paras
                logging.error(f"span does not match: {s} for {session_id}")
            else:
                attendant['begin_anchor'] = a_info['begin_anchor']
                attendant['end_anchor'] = a_info['end_anchor']
                attendant['begin_char_offset'] = a_info['begin_char_offset']
                attendant['end_char_offset'] = a_info['end_char_offset']

                attendant_annots.append(attendant)

    return attendant_annots


# blijkbaar komen er sessies voor zonder attendance_list. Check dit even

for sess in asearch.get_annotations_of_type('session', all_annotations, resource_id):
    alists = list(asearch.get_annotations_of_type_overlapping('attendance_list', \
                                                              sess['begin_anchor'], sess['end_anchor'], all_annotations,
                                                              resource_id))
    if len(alists) == 0:
        logging.warning(f"session {sess['id']} has no attendance_list")

attendant_annotations = []
for al in asearch.get_annotations_of_type('attendance_list', all_annotations, resource_id):
    session_id = al['metadata']['session_id']
    atts = create_attendants_for_attlist(al, session_id, resource_id)
    attendant_annotations.extend(atts)

all_annotations.extend(attendant_annotations)


# assume that iiif_urls refer to the same image resource
def union_of_iiif_urls(urls):
    # check if urls contain same image_identifier
    img_id = image_id_pattern.search(urls[0]).group(2)

    # for each url, find left, right, top, bottom
    boxes = []
    for url in urls:
        i_id = image_id_pattern.search(url)
        if image_id_pattern.search(url).group(2) != img_id:
            # print(f'\t{urls[0]}')
            logging.error(f"{url} refers to other image than {img_id}")
            break

        region_string = region_pattern.search(url)
        region = {"left": int(region_string.group(2)), \
                  "right": int(region_string.group(2)) + int(region_string.group(4)), \
                  "top": int(region_string.group(3)), \
                  "bottom": int(region_string.group(3)) + int(region_string.group(5))}
        boxes.append(region)

    min_left = min(box['left'] for box in boxes)
    max_right = max(box['right'] for box in boxes)
    min_top = min(box['top'] for box in boxes)
    max_bottom = max(box['bottom'] for box in boxes)
    height = max_bottom - min_top
    width = max_right - min_left

    # construct iiif_url by replacing coordinate part in first input url
    bounding_region_str = f"{min_left},{min_top},{width},{height}"
    bounding_url = re.sub(r'(\d+),(\d+),(\d+),(\d+)', rf'{bounding_region_str}', urls[0])

    return bounding_url


# vraag alle page annotations op
pg_annots = list(asearch.get_annotations_of_type('page', all_annotations, resource_id))

for pa in pg_annots:
    # per page, vraag alle overlappende text_regions op
    overlapping_regions = list(asearch.get_annotations_of_type_overlapping('text_region', \
                                                                           pa['begin_anchor'], pa['end_anchor'],
                                                                           all_annotations, resource_id))

    # verzamel alle iiif_urls daarvan en unificeer die
    urls = [tr['metadata']['iiif_url'] for tr in overlapping_regions]
    bounding_url = union_of_iiif_urls(urls)
    region_links = [bounding_url]

    pa['region_links'] = region_links

# vraag alle sessions op
s_annots = list(asearch.get_annotations_of_type('session', all_annotations, resource_id))

for s in s_annots:
    # per session, vraag alle text_regions op
    overlapping_regions = list(asearch.get_annotations_of_type_overlapping('text_region', \
                                                                           s['begin_anchor'], s['end_anchor'],
                                                                           all_annotations, resource_id))

    # verzamel alle iiif_urls daarvan en zet ze in volgorde in 'region_links'
    overlapping_regions.sort(key=lambda r_ann: r_ann['begin_anchor'])

    urls = [tr['metadata']['iiif_url'] for tr in overlapping_regions]
    s['region_links'] = urls


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


# vraag alle lines op
line_annots = list(asearch.get_annotations_of_type('line', all_annotations, resource_id))

# voeg iiif region_links toe aan alle line annotaties
for line in line_annots:
    coords = line['coords']
    bb = get_bounding_box_for_coords(coords)
    bb_str = f"{bb['left']},{bb['top']},{bb['width']},{bb['height']}"
    scan_id = line['metadata']['scan_id']
    items = scan_id.split('_')

    region_url = f"{iiif_base}{items[0]}_{items[1]}/{items[2]}/{scan_id}.jpg/{bb_str}{iiif_extension}"
    region_links = [region_url]
    line['region_links'] = region_links

for ann_type in line_based_types:
    print(f"Starting with annotation type {ann_type}")
    annots = list(asearch.get_annotations_of_type(ann_type.value, all_annotations, resource_id))

    for num, ann in enumerate(annots):
        ann_region_links = []

        # voor iedere resolutie, vraag overlappende regions        
        overlapping_regions = list(asearch.get_annotations_of_type_overlapping('text_region', \
                                                                               ann['begin_anchor'], ann['end_anchor'],
                                                                               all_annotations, resource_id))
        overlapping_regions.sort(key=lambda reg_ann: reg_ann['begin_anchor'])

        lines_in_annotation = list(asearch.get_annotations_of_type_overlapping('line', \
                                                                               ann['begin_anchor'], ann['end_anchor'],
                                                                               all_annotations, resource_id))

        # bepaal bounding box voor met RESOLUTION overlappende lines, per text_region
        for tr in overlapping_regions:
            lines_in_region = list(asearch.get_annotations_of_type_overlapping('line', \
                                                                               tr['begin_anchor'], tr['end_anchor'],
                                                                               all_annotations, resource_id))

            lines_in_intersection = [l for l in lines_in_annotation if l in lines_in_region]

            # determine iiif url region enclosing the line boxes, assume each line has only one url
            urls = [l['region_links'][0] for l in lines_in_intersection]
            region_url = union_of_iiif_urls(urls)
            ann_region_links.append(region_url)

            # generate output to report potential issues with layout of text_regions
            region_string = region_pattern.search(region_url)
            width = int(region_string.group(4))
            if width > 1000:
                logging.warning(f"potential error in layout, width of text_region {tr['id']} too large: {width}")
        ann['region_links'] = ann_region_links
        if num % 100 == 0:
            print(f"{num} annotations of type {ann_type} processed")

region_annots = list(asearch.get_annotations_of_type('text_region', all_annotations, resource_id))
for ra in region_annots:
    ra['region_links'] = [ra['metadata']['iiif_url']]

scan_annots = list(asearch.get_annotations_of_type('scan', all_annotations, resource_id))
for sa in scan_annots:
    sa['iiif_url'] = re.sub(r'(\d+),(\d+),(\d+),(\d+)/(max)', r'\5/,\4', sa['iiif_url'])
    sa['region_links'] = [sa['iiif_url']]

for a in all_annotations:
    a["provenance"] = provenance_data
    if "metadata" in a and "index_timestamp" in a["metadata"]:
        print(a["id"])
        a["provenance"]["index_timestamp"] = a["metadata"]["index_timestamp"]


def add_segmented_text_to_store(segmented_text, store_name):
    try:
        with open(datadir + store_name, 'r') as filehandle:
            data = json.loads(filehandle.read())
    except FileNotFoundError:
        data = {'_resources': []}

    data['_resources'].append(segmented_text)

    with open(datadir + store_name, 'w') as filehandle:
        json.dump(data, filehandle, indent=4, cls=segmentedtext.SegmentEncoder)


add_segmented_text_to_store(all_textlines, text_store)


def add_annotations_to_store(annotations, store_name):
    try:
        with open(datadir + store_name, 'r') as filehandle:
            data = json.loads(filehandle.read())
    except FileNotFoundError:
        data = []

    data.extend(annotations)

    with open(datadir + store_name, 'w') as filehandle:
        json.dump(data, filehandle, indent=4, cls=segmentedtext.AnchorEncoder)


add_annotations_to_store(all_annotations, annotation_store)
