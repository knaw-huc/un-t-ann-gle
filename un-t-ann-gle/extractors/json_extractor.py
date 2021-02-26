import glob
import json
import re

from textservice import segmentedtext

# read files

all_text_lines = segmentedtext.IndexedSegmentedText()
all_annotations = []


# We want to load 'text containers' that contain more or less contiguous text and are as long as practically
# possible. Container size is determined by pragmatic reasons, e.g. technical (performance) or user driven
# (corresponding with all scans in a book or volume). This functions returns all component files IN TEXT ORDER.
# Examples: sorted list of files, part of IIIF manifest.

def get_file_sequence_for_container(text_container):
    path = "../data/sessions/meeting-1705*"
    session_file_names = (f for f in glob.glob(path))
    return sorted(session_file_names)


# Many file types contain a hierarchy of ordered text and/or annotation elements of different types. Some form of
# depth-first, post order traversal is necessary. Examples: processing a json hierarchy with dictionaries
# and lists (republic) or parsing TEI XML (DBNL document).

def traverse(node, node_label, text, annotations):
    # find the list that represents the children, each child is a dict, assume first list is the correct one
    children = []
    label_of_children = ''
    for key, val in node.items():
        if type(val) == list:
            children = val
            label_of_children = key
            break

    if 'coords' in node:
        coords = node['coords']
    else:
        coords = None

    begin_index = text.len()
    annotation_info = {'label': node_label, 'image_coords': coords, 'begin_anchor': begin_index}
    if len(children) == 0:  # if no children, do your 'leaf node thing'
        annotation_info['id'] = node['id']
        annotation_info['end_anchor'] = text.len()
        node_text = node['text']

        if node_text is None:
            node_text = '\n'

        text.append(node_text)
    else:  # if non-leaf node, first visit children
        for child in children:
            traverse(child, label_of_children, text, annotations)

        # ONDERSTAANDE IS SMERIG, hangt van onzekere aannames af
        for k in node['metadata'].keys():
            idkey = ''
            if k.endswith('id'):
                idkey = k
                break
        annotation_info['id'] = node['metadata'][idkey]

        end_index = text.len() - 1
        annotation_info['end_anchor'] = end_index  # after child text segments are added

        # if node contains iiif_url, create extra annotation_info for 'scanpage'
        if 'iiif_url' in node['metadata']:
            scan_annot_info = {'label': 'scanpage', 'iiif_url': node['metadata']['iiif_url'],
                               'begin_anchor': begin_index, 'end_anchor': end_index,
                               'scan_num': node['metadata']['scan_num']}
            annotations.append(scan_annot_info)

    annotations.append(annotation_info)
    return


# In case of presence of a hierarchical structure, processing/traversal typically starts from a root element.

def get_root_tree_element(file):
    with open(file, 'r') as myfile:
        session_file = myfile.read()

    session_data = json.loads(session_file)
    return session_data['_source']


# Rudimentary version of a scanpage_handler

def deduplicate_scanpage_annotations(a_array):
    # use a generator to create a list of only scanpage annotation_info dicts
    scan_page_annots = [ann_info for ann_info in a_array if ann_info['label'] == 'scanpage']

    # use groupBy on a list of dicts (zie Python cookbook 1.15)
    from operator import itemgetter
    from itertools import groupby

    # first sort on scan_num
    scan_page_annots.sort(key=itemgetter('scan_num'))

    # iterate in groups
    aggregated_scan_annots = []

    for scan_num, items in groupby(scan_page_annots, key=itemgetter('scan_num')):
        # first, convert the 'items' iterator to a list, to able to use it twice (iterators can be used once)
        itemlist = list(items)

        # copy the item with the lowest begin_index
        aggr_scan_annot = min(itemlist, key=itemgetter('begin_anchor')).copy()

        # replace 'end_anchor' with the highest end_index in the group
        max_end_index = max(itemlist, key=itemgetter('end_anchor'))['end_anchor']
        aggr_scan_annot['end_anchor'] = max_end_index

        # add to result
        aggregated_scan_annots.append(aggr_scan_annot)

    #    for scan_ann in aggregated_scan_annots:
    #        scan_ann['iiif_url'] = re.sub(r'(\d+),(\d+),(\d+),(\d+)/(full)', r'\5/,\4', scan_ann['iiif_url'])

    a_array = [ann for ann in a_array if ann not in scan_page_annots]
    a_array.extend(aggregated_scan_annots)

    return


def correct_scanpage_imageurls(a_array):
    scan_page_annots = [ann_info for ann_info in a_array if ann_info['label'] == 'scanpage']

    for scan_ann in scan_page_annots:
        scan_ann['iiif_url'] = re.sub(r'(\d+),(\d+),(\d+),(\d+)/(full)', r'\5/,\4', scan_ann['iiif_url'])

    return


# Rudimentary version of a page_handler

def add_page_annotations(source_data, ann_array):
    page_data = source_data['page_versions']

    # generator
    page_identifiers = (pg['page_id'] for pg in page_data)
    page_annots = [{'label': 'pages', 'id': page_id} for page_id in page_identifiers]

    for pa in page_annots:
        scan_num = int(re.search(r'(\d+)-page-', pa['id']).group(1))
        scanpage_for_scan_num = [ai for ai in ann_array if 'scan_num' in ai.keys() and ai['scan_num'] == \
                                 scan_num]
        pa['begin_anchor'] = scanpage_for_scan_num[0]['begin_anchor']
        pa['end_anchor'] = scanpage_for_scan_num[0]['end_anchor']
        pa['indexesByContainment'] = True

    ann_array.extend(page_annots)
    return


# Process per file, properly concatenate results, maintaining proper referencing the baseline text elements
def process(sourcefile_paths: list) -> (list, list):
    text_array = segmentedtext.IndexedSegmentedText()
    annotation_array = []

    for path in sourcefile_paths:
        source_data = get_root_tree_element(path)

        traverse(source_data, 'sessions', text_array, annotation_array)

        scanpages = deduplicate_scanpage_annotations(annotation_array)
        correct_scanpage_imageurls(annotation_array)

        add_page_annotations(source_data, annotation_array)

        # properly concatenate annotation info taking ongoing line indexes into account
        for ai in annotation_array:
            ai['begin_anchor'] += all_text_lines.len()
            ai['end_anchor'] += all_text_lines.len()

        all_text_lines.extend(text_array)
        all_annotations.extend(annotation_array)

    return all_text_lines, all_annotations
