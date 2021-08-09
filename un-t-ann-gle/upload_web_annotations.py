import json
import random
from itertools import groupby

from rdflib import Graph

from annotations import LineAnnotation, AttendantAnnotation, AttendantsListAnnotation, ColumnAnnotation, \
    ResolutionAnnotation, ScanPageAnnotation, SessionAnnotation, TextRegionAnnotation


def scanpage_as_web_annotation(annotation: dict) -> dict:
    return ScanPageAnnotation.from_dict(annotation).as_web_annotation()


def column_as_web_annotation(annotation: dict) -> dict:
    return ColumnAnnotation.from_dict(annotation).as_web_annotation()


def textregion_as_web_annotation(annotation: dict) -> dict:
    return TextRegionAnnotation.from_dict(annotation).as_web_annotation()


def line_as_web_annotation(annotation: dict) -> dict:
    return LineAnnotation.from_dict(annotation).as_web_annotation()


def session_as_web_annotation(annotation: dict) -> dict:
    return SessionAnnotation.from_dict(annotation).as_web_annotation()


def attendantslist_as_web_annotation(annotation: dict) -> dict:
    return AttendantsListAnnotation.from_dict(annotation).as_web_annotation()


def attendant_as_web_annotation(annotation: dict) -> dict:
    return AttendantAnnotation.from_dict(annotation).as_web_annotation()


def resolution_as_web_annotation(annotation: dict) -> dict:
    return ResolutionAnnotation.from_dict(annotation).as_web_annotation()


annotation_mapper = {
    'scanpage': scanpage_as_web_annotation,
    'columns': column_as_web_annotation,
    'textregions': textregion_as_web_annotation,
    'lines': line_as_web_annotation,
    'sessions': session_as_web_annotation,
    'attendantslists': attendantslist_as_web_annotation,
    'attendants': attendant_as_web_annotation,
    'resolutions': resolution_as_web_annotation
}


def as_web_annotation(annotation: dict) -> dict:
    # ic(annotation)
    label = annotation.get('label')
    return annotation_mapper[label](annotation)


def main():
    input = 'data/1728/10mrt-v1/1728-annotationstore.json'
    print(f'> importing {input} ...')
    with open(input) as f:
        annotations = json.load(f)
    print(f'> {len(annotations)} annotations loaded')

    print_example_conversions(annotations)

    print(f'> converting ...')
    web_annotations = [as_web_annotation(annotation) for annotation in annotations]

    out_file = 'web_annotations.json'
    print(f'> exporting to {out_file} ...')
    with open(out_file, 'w') as out:
        json.dump(web_annotations, out, indent=4)

    print('> done!')


def print_example_conversions(annotations):
    key_func = lambda a: a['label']
    grouped_annotations = groupby(sorted(annotations, key=key_func), key=key_func)
    for label, group in grouped_annotations:
        print(f"label: *{label}*")
        random_annotation = random.choice(list(group))
        print(f"original annotation:\n{{code}}\n{json.dumps(random_annotation, indent=2)}\n{{code}}")
        web_annotation = as_web_annotation(random_annotation)
        print(f"W3C Web annotation:\n{{code}}\n{json.dumps(web_annotation, indent=2)}\n{{code}}")
        jsonld = json.dumps(web_annotation)
        g = Graph()
        g.parse(data=jsonld, format="json-ld")
        ttl = g.serialize(format="ttl")
        print(f"W3C Web annotation as turtle:\n{{code}}\n{ttl}\n{{code}}")
        print("----")


if __name__ == '__main__':
    main()
