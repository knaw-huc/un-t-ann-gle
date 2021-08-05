from datetime import datetime
from typing import Any

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
class LinesAnnotation:
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords

    def as_web_annotation(self) -> dict:
        body = classifying_body('lines', self.id)
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(self.image_coords)]
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


def image_target(image_coords: ImageCoords,
                 iiif_url: str = "https://example.org/missing-iiif-url",
                 scan_id: str = None) -> dict:
    xywh = f"{image_coords.left},{image_coords.top},{image_coords.width},{image_coords.height}"
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
