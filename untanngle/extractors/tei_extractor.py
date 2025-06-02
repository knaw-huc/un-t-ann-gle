import uuid

from lxml import etree

from untanngle.textservice import segmentedtext

_last_page_begin_index = 0
_last_section_begin_index = -1
_last_chapter_begin_index = -1
_last_paragraph_begin_index = -1
_last_head_begin_index = -1

_last_page_end_index = -1
_last_section_end_index = -1
_last_chapter_end_index = -1
_last_paragraph_end_index = -1
_last_head_end_index = -1

_last_page_id = ""

all_text_elements = segmentedtext.SplittableSegmentedText()
all_annotations = []


def get_root_tree_element(path: str):
    # use iterparse to traverse the xml hierarchy, depth first, post order
    return etree.iterparse(path, events=('start', 'end'))


# handle each of the elements in the hierarchy according to 'layer type'
def handle_element(action, e, text, annotations):
    global _last_page_begin_index
    global _last_section_begin_index
    global _last_chapter_begin_index
    global _last_paragraph_begin_index
    global _last_head_begin_index

    global _last_page_end_index
    global _last_section_end_index
    global _last_chapter_end_index
    global _last_paragraph_end_index
    global _last_head_end_index

    global _last_page_id

    if action == 'start':
        # store last begin indexes
        if e.tag == 'p':
            _last_paragraph_begin_index = text.len()
        elif e.tag == 'div' and e.get('type') == 'chapter':
            _last_chapter_begin_index = text.len()
        elif e.tag == 'div' and e.get('type') == 'section':
            _last_section_begin_index = text.len()
        elif e.tag == 'head':
            _last_head_begin_index = text.len()
    elif action == 'end':
        if e.tag == 'p':
            # leaf text element, add to all_textelements, also include text after possible pb's
            for index, t in enumerate(e.itertext()):
                text.append(t.strip())
                if index > 0:  # assume: caused by pb contained within p. Update page end.
                    _last_page_end_index = text.len() - 1

            _last_paragraph_end_index = text.len() - 1

            if _last_paragraph_begin_index <= _last_paragraph_end_index:
                annotations.append({'label': 'paragraph', 'begin_anchor': text._anchors[_last_paragraph_begin_index],
                                    'end_anchor': text._anchors[_last_paragraph_end_index],
                                    'id': 'annot_' + str(uuid.uuid4())})
        elif e.tag == 'head':
            # leaf text element, add to all_textelements
            text.append(e.text)

            _last_head_end_index = text.len() - 1
            annotations.append({'label': 'head', 'begin_anchor': text._anchors[_last_head_begin_index],
                                'end_anchor': text._anchors[_last_head_end_index], 'id': 'annot_' + str(uuid.uuid4())})
        elif e.tag == 'div' and e.get('type') == 'chapter':
            _last_chapter_end_index = text.len() - 1
            annotations.append({'label': 'chapter', 'begin_anchor': text._anchors[_last_chapter_begin_index],
                                'end_anchor': text._anchors[_last_chapter_end_index],
                                'id': 'annot_' + str(uuid.uuid4())})
        elif e.tag == 'div' and e.get('type') == 'section':
            _last_section_end_index = text.len() - 1
            annotations.append({'label': 'section', 'begin_anchor': text._anchors[_last_section_begin_index],
                                'end_anchor': text._anchors[_last_section_end_index],
                                'id': 'annot_' + str(uuid.uuid4())})
        elif e.tag == 'pb':
            # first store the 'previous' page, then store begin and end of currently closed page
            annotations.append({'label': 'page', 'begin_anchor': text._anchors[_last_page_begin_index],
                                'end_anchor': text._anchors[_last_page_end_index], 'id': _last_page_id})
            _last_page_begin_index = _last_page_end_index
            _last_page_end_index = text.len() - 1
            _last_page_id = f"page-{e.get('n')}"

    return


def traverse(node, node_label, text, annotations):
    for action, elem in node:
        handle_element(action, elem, text, annotations)
    return


# Process per file, properly concatenate results, maintaining proper referencing the baseline text elements
def process(sourcefile_paths: list) -> (list, list):
    text_segments = segmentedtext.SplittableSegmentedText()
    annotation_array = []

    for path in sourcefile_paths:
        source_data = get_root_tree_element(path)

        traverse(source_data, '', text_segments, annotation_array)

        # properly concatenate annotation info taking ongoing line indexes into account - trivial, do not apply in this case
        #    for ai in annotation_array:
        #        ai['begin_index'] += len(all_textlines)
        #        ai['end_index'] += len(all_textlines)

        all_text_elements.extend(text_segments)
        all_annotations.extend(annotation_array)

    return all_text_elements, all_annotations
