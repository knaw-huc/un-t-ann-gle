from datetime import datetime
from typing import Any, List, Union

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, Undefined, config


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class Metadata:
    offset: int
    end: int
    metadata_class: str = field(metadata=config(field_name="class"))
    pattern: str
    delegate_id: int
    delegate_name: str
    delegate_score: float


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ImageCoords:
    left: int
    right: int
    top: int
    bottom: int
    height: int
    width: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantsAnnotation:
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    metadata: Metadata

    def as_web_annotation(self) -> dict:
        body = [classifying_body('attendants', self.id),
                dataset_body(self.metadata)]
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor)]
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantsListsAnnotation:
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    session_id: str
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    # TODO: add session_id to body, add image_range + region_links to target
    def as_web_annotation(self) -> dict:
        body = [classifying_body('attendantslists', self.id)
                ]
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor)]
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ResolutionsAnnotation:
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    proposition_type: Union[str, None]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    # TODO: add proposition_type to body, image_range + region_links to target
    def as_web_annotation(self) -> dict:
        body = [classifying_body('resolutions', self.id)
                ]
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor)]
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ColumnsAnnotation:
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords

    def as_web_annotation(self) -> dict:
        body = classifying_body('columns', self.id)
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(image_coords=self.image_coords)]
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class LinesAnnotation:
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords

    def as_web_annotation(self) -> dict:
        body = classifying_body('lines', self.id)
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(image_coords=self.image_coords)]
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ScanPageAnnotation:
    scan_id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    iiif_url: str

    def as_web_annotation(self) -> dict:
        body = classifying_body('scanpage', self.scan_id)
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(iiif_url=self.iiif_url)]
        return web_annotation(body=body, target=target)


def classifying_body(value: str, id: str):
    body = {
        "type": "TextualBody",
        "purpose": "classifying",
        "value": value
    }
    if id:
        body['id'] = id
    return body


def dataset_body(metadata: Metadata):
    dataset_body = {
        "type": "Dataset",
        "value": metadata.__dict__
    }
    return dataset_body


def resource_target(resource_id, begin_anchor, end_anchor):
    return {
        "source": resource_id,
        "selector": {
            "type": "TextAnchorSelector",
            "start": begin_anchor,
            "end": end_anchor
        }
    }


def image_target(iiif_url: str = "https://example.org/missing-iiif-url",
                 image_coords: ImageCoords = None,
                 scan_id: str = None) -> dict:
    image_target = {
        "source": iiif_url,
        "type": "image"
    }
    if image_coords:
        xywh = f"{image_coords.left},{image_coords.top},{image_coords.width},{image_coords.height}"
        image_target['selector'] = {
            "type": "FragmentSelector",
            "conformsTo": "http://www.w3.org/TR/media-frags/",
            "value": f"xywh={xywh}"
        }
    if scan_id:
        image_target['id'] = scan_id
    return image_target


def web_annotation(body: Any, target: Any) -> dict:
    return {
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
        "target": target
    }


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
