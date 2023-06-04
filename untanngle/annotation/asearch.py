"""
This module contains candidate functions for an annotation service for annotations
that are connected to a segmented text object.
"""


def get_annotations_at_anchor(anchor, annotations, label=None):
    annots_at_anchor = [ann_info for ann_info in annotations if
                        ann_info['begin_anchor'] <= anchor <= ann_info['end_anchor']]
    return annots_at_anchor


def get_annotations_of_type(type, annotations, resource_id=None):
    """
	Returns a generator for annotations of a specific type.

	This function returns a generator for all annotations of the specified type
	from the list of all annotations.
    """
    annotations_for_resource = annotations
    if resource_id is not None:
        annotations_for_resource = (a for a in annotations if a['resource_id'] == resource_id)
    return (a for a in annotations_for_resource if a['type'] == type)


def get_annotations_overlapping_with(begin_anchor, end_anchor, annotations, resource_id):
    """
    Returns all annotations that overlap with a specific text interval.

    This function should work for all indexes or anchors that support comparison operations.
    """
    return (a for a in annotations if (a['resource_id'] == resource_id) and \
            ((begin_anchor <= a['begin_anchor'] < end_anchor) or
             (begin_anchor < a['end_anchor'] <= end_anchor) or
             (a['begin_anchor'] <= begin_anchor and a['end_anchor'] >= end_anchor)))


def matches_filters(annotation, filters):
    if filters is None or len(filters) == 0:
        return True

    if 'type' in filters and annotation['type'] != filters['type']:
        return False

    if 'owner' not in filters:
        return True

    if 'owner' not in annotation or annotation['owner'] != filters['owner']:
        return False

    return True


#    if annotation['label'] == filters['type']:
#    	return True

#    if annotation['owner'] == filters['owner']:
#        return True
#    else:
#    	return False

def get_filtered_annotations_overlapping(filters, begin, end, annotations, resource_id):
    """
    Returns all annotations of that overlap with a specific text interval and match the filters.
    """
    return filter(lambda annotation: matches_filters(annotation, filters),
                  (get_annotations_overlapping_with(begin, end, annotations, resource_id)))


def get_annotations_of_type_overlapping(type, begin, end, annotations, resource_id):
    """
    Returns all annotations of a specific type that overlap with a specific text interval.
    """
    return get_annotations_of_type(type, (get_annotations_overlapping_with(begin, end, annotations, resource_id)))


def get_annotations_of_types(types, annotations, resource_id=None):
    """
    Returns all annotations of a list of given types.
    """
    annotations_for_resource = annotations
    if resource_id is not None:
        annotations_for_resource = (a for a in annotations if a['resource_id'] == resource_id)
    return (a for a in annotations_for_resource if a['type'] in types)


def get_annotations_of_types_overlapping(types, begin, end, annotations, resource_id):
    """
    Return all annotations of the given types that overlap with a specific text interval.
    """
    return get_annotations_of_types(types, (get_annotations_overlapping_with(begin, end, annotations, resource_id)))


def get_annotation_by_id(ann_id, annotations):
    for ann in annotations:
        if 'id' in ann and ann['id'] == ann_id:
            return ann
    return None
