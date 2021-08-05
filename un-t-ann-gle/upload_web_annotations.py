import json

from icecream import ic

from annotations import LineAnnotation, AttendantAnnotation, AttendantsListAnnotation, ColumnAnnotation, \
    ResolutionAnnotation, classifying_annotation_mapper, ScanPageAnnotation, SessionAnnotation


def scanpage_as_web_annotation(annotation: dict) -> dict:
    return ScanPageAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'scanpage')


def column_as_web_annotation(annotation: dict) -> dict:
    return ColumnAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'columns')


def line_as_web_annotation(annotation: dict) -> dict:
    return LineAnnotation.from_dict(annotation).as_web_annotation()


def session_as_web_annotation(annotation: dict) -> dict:
    ic(annotation)
    return SessionAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'sessions')


def attendantslist_as_web_annotation(annotation: dict) -> dict:
    return AttendantsListAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'attendantslists')


def attendant_as_web_annotation(annotation: dict) -> dict:
    return AttendantAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'attendants')


def resolution_as_web_annotation(annotation: dict) -> dict:
    return ResolutionAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'resolutions')


def textregion_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'textregions')


annotation_mapper = {
    'attendants': attendant_as_web_annotation,
    'attendantslists': attendantslist_as_web_annotation,
    'columns': column_as_web_annotation,
    'lines': line_as_web_annotation,
    'resolutions': resolution_as_web_annotation,
    'scanpage': scanpage_as_web_annotation,
    'sessions': session_as_web_annotation,
    'textregions': textregion_as_web_annotation
}


def as_web_annotation(annotation: dict) -> dict:
    # ic(annotation)
    label = annotation.pop('label')
    return annotation_mapper[label](annotation)


def main():
    input = 'data/1728/10mrt-v1/1728-annotationstore.json'
    print(f'> importing {input} ...')
    with open(input) as f:
        annotations = json.load(f)
    print(f'> {len(annotations)} annotations loaded')

    print(f'> converting ...')
    web_annotations = [as_web_annotation(annotation) for annotation in annotations]

    out_file = 'web_annotations.json'
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(web_annotations, out, indent=4)

    print('> done!')


if __name__ == '__main__':
    main()
