"""
This module contains candidate functions for an annotation service for annotations
that are connected to a segmented text object.
"""

# managed list of annotations. For the moment set by a POST operation
managed_annotations = []


def get_annotations_at_anchor(anchor, annotations, label=None):
    annots_at_anchor = [ann_info for ann_info in annotations if
                        ann_info['begin_anchor'] <= anchor <= ann_info['end_anchor']]
    return annots_at_anchor


def get_annotations_of_type(type, annotations):
    """
	Returns a generator for annotations of a specific type.

	This function returns a generator for all annotations of the specified type
	from the list of all annotations.
    """
    return (a for a in annotations if a['label'] == type)


def get_annotations_overlapping_with(begin_anchor, end_anchor, annotations):
    """
    Returns all annotations that overlap with a specific text interval.

    This function should work for all indexes or anchors that support comparison operations.
    """
    return (a for a in annotations if (begin_anchor <= a['begin_anchor'] < end_anchor) or \
            (begin_anchor < a['end_anchor'] <= end_anchor) or \
            (a['begin_anchor'] <= begin_anchor and a['end_anchor'] >= end_anchor))


def get_annotations_of_type_overlapping(type, begin, end, annotations):
    """
    Returns all annotations of a specific type that overlap with a specific text interval.
    """
    return get_annotations_of_type(type, (get_annotations_overlapping_with(begin, end, annotations)))


def get_annotations_of_types(types, annotations):
    """
    Returns all annotations of a list of given types.
    """
    return (a for a in annotations if a['label'] in types)


def get_annotations_of_types_overlapping(types, begin, end, annotations):
    """
    Return all annotations of the given types that overlap with a specific text interval.
    """
    return get_annotations_of_types(types, (get_annotations_overlapping_with(begin, end, annotations)))


def get_annotation_by_id(id, annotations):
    return next(ann for ann in annotations if 'id' in ann.keys() and ann['id'] == id)