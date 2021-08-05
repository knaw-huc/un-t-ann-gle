from datetime import datetime
from typing import Any

from dataclasses import dataclass
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class ImageCoords:
    left: int
    right: int
    top: int
    bottom: int
    height: int
    width: int


@dataclass_json
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
