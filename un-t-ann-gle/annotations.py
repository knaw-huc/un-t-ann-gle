import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Union, Dict

import uri as uri
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
class ScanPageAnnotation:
    label: str
    scan_id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    iiif_url: str
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def as_web_annotation(self) -> dict:
        body = classifying_body(id=as_urn(self.scan_id), value='scanpage')
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(iiif_url=self.iiif_url)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ColumnAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def as_web_annotation(self) -> dict:
        body = classifying_body(as_urn(self.id), 'column')
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(image_coords=self.image_coords)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class TextRegionAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords
    iiif_url: Union[str, None]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def __post_init__(self):
        self.id = re.sub(r'-line-.*', '', self.id)

    def as_web_annotation(self) -> dict:
        body = classifying_body(as_urn(self.id), 'textregion')
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(iiif_url=self.iiif_url, image_coords=self.image_coords)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class LineAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords
    iiif_url: Union[str, None]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def as_web_annotation(self) -> dict:
        body = classifying_body(as_urn(self.id), 'line')
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(iiif_url=self.iiif_url, image_coords=self.image_coords)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class SessionAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: Union[None, ImageCoords]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]
    session_date: str
    session_year: int
    session_weekday: str
    president: Union[None, str]

    def as_web_annotation(self) -> dict:
        body = [classifying_body(as_urn(self.id), 'session'),
                dataset_body({"date": self.session_date,
                              "year": self.session_year,
                              "weekday": self.session_weekday,
                              "president": self.president})]
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor),
                  image_target(image_coords=self.image_coords)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantsListAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    session_id: str
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    # TODO: add session_id to body, add image_range + region_links to target
    def as_web_annotation(self) -> dict:
        body = [
            classifying_body(as_urn(self.id), 'attendantslist'),
            {"partOf": as_urn(self.session_id)}
        ]
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    metadata: Metadata
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def as_web_annotation(self) -> dict:
        body = [classifying_body(as_urn(self.id), 'attendant'),
                dataset_body(self.metadata.__dict__)]
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ResolutionAnnotation:
    label: str
    id: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    proposition_type: Union[str, None]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    # TODO: add proposition_type to body, image_range + region_links to target
    def as_web_annotation(self) -> dict:
        body = [classifying_body(as_urn(self.id), 'resolution')]
        if self.proposition_type:
            body.append({"proposition_type": self.proposition_type})
        target = [resource_target(self.resource_id, self.begin_anchor, self.end_anchor)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))

        return web_annotation(body=body, target=target)


def classifying_body(id: str, value: str):
    body = {
        "type": "TextualBody",
        "purpose": "classifying",
        "value": value
    }
    if id:
        body['id'] = id
    return body


def dataset_body(metadata: Dict):
    dataset_body = {
        "type": "Dataset",
        "value": metadata
    }
    return dataset_body


def resource_target(resource_id, begin_anchor, end_anchor):
    return {
        "source": resource_id,
        "selector": {
            "type": as_urn("TextAnchorSelector"),
            "start": begin_anchor,
            "end": end_anchor
        }
    }


def image_target(iiif_url: str = "https://example.org/missing-iiif-url",
                 image_coords: ImageCoords = None,
                 scan_id: str = None) -> dict:
    image_target = {
        "source": iiif_url,
        "type": "Image"
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


roar_context = {
    "roar": "https://w3id.org/roar#",
    "Document": "roar:Document",
    "Entity": "roar:Entity",
    "Location": "roar:Location",
    "LocationObservation": "roar:LocationObservation",
    "LocationReconstruction": "roar:LocationReconstruction",
    "Observation": "roar:Observation",
    "Person": "roar:Person",
    "PersonObservation": "roar:PersonObservation",
    "PersonReconstruction": "roar:PersonReconstruction",
    "Reconstruction": "roar:Reconstruction",
    "documentedIn": "roar:documentedIn",
    "hasLocation": "roar:hasLocation",
    "hasPerson": "roar:hasPerson",
    "hasRelation": "roar:hasRelation",
    "locationInDocument": "roar:locationInDocument",
    "onScan": "roar:onScan",
    "relationType": "roar:relationType",
    "role": "roar:role"
}


def web_annotation(body: Any,
                   target: Any,
                   id: uri = f"urn:example:republic:annotation:{uuid.uuid4()}",
                   custom: dict = None) -> dict:
    annotation = {
        "@context": [
            "http://www.w3.org/ns/anno.jsonld",
            # roar_context
        ],
        "id": id,
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
    if custom:
        annotation.update(custom)
    return annotation


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
            "type": as_urn("TextAnchorSelector"),
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
            "type": "Image",
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
                "type": "Image",
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


def as_urn(id: str) -> str:
    return f"urn:example:republic:{id}"
