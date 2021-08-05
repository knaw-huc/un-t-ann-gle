import json

from icecream import ic

from annotations import LinesAnnotation, AttendantsAnnotation, AttendantsListsAnnotation, ColumnsAnnotation, \
    ResolutionsAnnotation, classifying_annotation_mapper, ScanPageAnnotation


def attendants_as_web_annotation(annotation: dict) -> dict:
    return AttendantsAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'attendants')


def attendantslists_as_web_annotation(annotation: dict) -> dict:
    return AttendantsListsAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'attendantslists')


def columns_as_web_annotation(annotation: dict) -> dict:
    return ColumnsAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'columns')


def lines_as_web_annotation(annotation: dict) -> dict:
    return LinesAnnotation.from_dict(annotation).as_web_annotation()


def resolutions_as_web_annotation(annotation: dict) -> dict:
    ic(annotation)
    return ResolutionsAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'resolutions')


def scanpage_as_web_annotation(annotation: dict) -> dict:
    return ScanPageAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'scanpage')


def sessions_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'sessions')


def textregions_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'textregions')


annotation_mapper = {
    'attendants': attendants_as_web_annotation,
    'attendantslists': attendantslists_as_web_annotation,
    'columns': columns_as_web_annotation,
    'lines': lines_as_web_annotation,
    'resolutions': resolutions_as_web_annotation,
    'scanpage': scanpage_as_web_annotation,
    'sessions': sessions_as_web_annotation,
    'textregions': textregions_as_web_annotation
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
