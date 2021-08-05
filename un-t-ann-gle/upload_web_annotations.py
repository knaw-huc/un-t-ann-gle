import json
from datetime import datetime

from icecream import ic

from annotations import LinesAnnotation, AttendantsAnnotation


def classifying_annotation_mapper(annotation: dict, value: str) -> dict:
    body = {
        "type": "TextualBody",
        "purpose": "classifying",
        "value": value
    }
    id = annotation.pop('id', None)
    if id:
        body['id'] = id
    if value == 'sessions':
        session_date = annotation.pop('session_date')
        session_year = annotation.pop('session_year')
        session_weekday = annotation.pop('session_weekday')
        president = annotation.pop('president')
        dataset_body = {
            "type": "Dataset",
            "value": {
                "session_date": session_date,
                "session_year": session_year,
                "session_weekday": session_weekday,
                "president": president
            }
        }
        body = [body, dataset_body]

    resource_id = annotation.pop('resource_id')
    begin_anchor = annotation.pop('begin_anchor')
    end_anchor = annotation.pop('end_anchor')
    targets = [{
        "source": resource_id,
        "selector": {
            "type": "TextAnchorSelector",
            "start": begin_anchor,
            "end": end_anchor
        }
    }]
    image_coords = annotation.pop('image_coords', None)
    scan_id = annotation.pop('scan_id', None)
    if image_coords:
        iiif_url = annotation.pop('iiif_url', "https://example.org/missing-iiif-url")
        xywh = f"{image_coords['left']},{image_coords['top']},{image_coords['width']},{image_coords['height']}"
        image_target = {
            "source": iiif_url,
            "type": "image",
            "selector": {
                "type": "FragmentSelector",
                "conformsTo": "http://www.w3.org/TR/media-frags/",
                "value": f"xywh={xywh}"
            }
        }
        if scan_id:
            image_target['id'] = scan_id
        targets.append(image_target)
    else:
        if scan_id:
            iiif_url = annotation.pop('iiif_url')
            image_target = {
                "id": scan_id,
                "source": iiif_url,
                "type": "image",
            }
            targets.append(image_target)

    if len(targets) > 1:
        target = targets
    else:
        target = targets[0]

    web_annotation = {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "type": "Annotation",
        "motivation": "classifying",
        "created": datetime.today().isoformat(),
        "generator": {
            "id": "https://github.com/knaw-huc/un-t-ann-gle",
            "type": "Software",
            "name": "un-t-ann-gle"
        },
        "body": body,
        "target": target,
        # "target": [
        #     {
        #         "source": f'{scan_urn}:textline={text_line.id}',
        #         "selector": {
        #             "type": "TextPositionSelector",
        #             "start": ner_result['offset']['begin'],
        #             "end": ner_result['offset']['end']
        #         }
        #     },
        #     {
        #         "source": f'{scan_urn}:textline={text_line.id}',
        #         "selector": {
        #             "type": "FragmentSelector",
        #             "conformsTo": "http://tools.ietf.org/rfc/rfc5147",
        #             "value": f"char={ner_result['offset']['begin']},{ner_result['offset']['end']}"
        #         }
        #     },
        #     {
        #         "source": f'{version_base_uri}/contents',
        #         "type": "xml",
        #         "selector": {
        #             "type": "FragmentSelector",
        #             "conformsTo": "http://tools.ietf.org/rfc/rfc3023",
        #             "value": f"xpointer(id({text_line.id})/TextEquiv/Unicode)"
        #         }
        #     },
        #     {
        #         "source": f"{version_base_uri}/chars/{ner_result['offset']['begin']}/{ner_result['offset']['end']}"
        #     },
        #     {
        #         "source": iiif_url,
        #         "type": "image",
        #         "selector": {
        #             "type": "FragmentSelector",
        #             "conformsTo": "http://www.w3.org/TR/media-frags/",
        #             "value": f"xywh={xywh}"
        #         }
        #     }
        # ]
    }
    if annotation:
        web_annotation["_unused_fields_from_original"] = annotation
    return web_annotation


def attendants_as_web_annotation(annotation: dict) -> dict:
    return AttendantsAnnotation.from_dict(annotation).as_web_annotation()
    # return classifying_annotation_mapper(annotation, 'attendants')


def attendantslists_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'attendantslists')


def columns_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'columns')


def lines_as_web_annotation(annotation: dict) -> dict:
    return LinesAnnotation.from_dict(annotation).as_web_annotation()


def resolutions_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'resolutions')


def scanpage_as_web_annotation(annotation: dict) -> dict:
    return classifying_annotation_mapper(annotation, 'scanpage')


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
    ic(annotation)
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
