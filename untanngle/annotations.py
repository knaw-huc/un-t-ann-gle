import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Union, Dict, Set, Optional

import requests
import uri as uri
from dataclasses_json import dataclass_json, Undefined, config
from rfc3987 import parse

from untanngle.camel_casing import keys_to_camel_case

REPUBLIC_CONTEXT = "https://brambg.github.io/ns/republic.jsonld"


def exclude_if_none(value):
    """Do not include field for None values"""
    return value is None


class Annotation:
    def as_web_annotation(self, textrepo_base_url: str, version_id: str) -> dict:
        target = []
        if hasattr(self, 'coords') and self.coords:
            if hasattr(self, 'iiif_url'):
                iiif_url = self.iiif_url
            else:
                first_region_link = self.region_links[0]
                iiif_url = re.sub(r'jpg/[\d,]+/', 'jpg/full/', first_region_link)
            image_coords = to_image_coords(self.coords)
            target.append(image_target(iiif_url=iiif_url, image_coords=image_coords))
            target.append(
                image_target_wth_svg_selector(iiif_url=iiif_url,
                                              coords=self.coords))
        else:
            for rl in self.region_links:
                xywh = rl.split('/')[-4]
                if "," in xywh:
                    (x, y, w, h) = xywh.split(',')
                    image_coords = ImageCoords(left=x, right=x + w, top=y, bottom=y + h, width=w, height=h)
                    iiif_url = re.sub(r'jpg/[\d,]+/', 'jpg/full/', rl)
                    target.append(image_target(iiif_url=iiif_url, image_coords=image_coords))

        if hasattr(self, 'begin_anchor'):
            if hasattr(self, 'end_char_offset'):
                target.append(
                    resource_target(
                        textrepo_base_url=textrepo_base_url,
                        version_id=version_id,
                        begin_anchor=self.begin_anchor,
                        end_anchor=self.end_anchor,
                        begin_char_offset=self.begin_char_offset,
                        end_char_offset=self.end_char_offset - 1
                    )
                )
                target.append(
                    selection_view_target(
                        textrepo_base_url=textrepo_base_url,
                        version_id=version_id,
                        begin_anchor=self.begin_anchor,
                        end_anchor=self.end_anchor,
                        begin_char_offset=self.begin_char_offset,
                        end_char_offset=self.end_char_offset - 1
                    )
                )
            else:
                target.append(resource_target(textrepo_base_url, version_id, self.begin_anchor, self.end_anchor))
                target.append(selection_view_target(textrepo_base_url, version_id, self.begin_anchor, self.end_anchor))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        body = self.body()
        if "metadata" in body.keys():
            if "id" in body["metadata"].keys():
                body["metadata"].pop("id")
                body["metadata"].pop("type")
        return web_annotation(body=body, target=target, provenance=self.provenance)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class Provenance:
    source: str
    target: str
    harvesting_date: str
    conversion_date: str
    tool_id: str
    motivation: str
    index_timestamp: str


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class Structure:
    type: str


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class MatchScores:
    char_match: float
    ngram_match: float
    levenshtein_similarity: float


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class Evidence:
    type: str
    phrase: str
    variant: str
    string: str
    offset: int
    label: str
    ignorecase: bool
    text_id: str
    match_scores: MatchScores


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
        target = [resource_target(self.begin_anchor, self.end_anchor),
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
        target = [resource_target(self.begin_anchor, self.end_anchor),
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
class TextRegionMetadata:
    id: str
    type: List[str]
    parent_type: str
    parent_id: str
    scan_id: str
    page_id: str
    iiif_url: str
    page_num: int
    text_page_num: int
    median_normal_left: Optional[int] = field(metadata=config(exclude=exclude_if_none), default=None)
    median_normal_right: Optional[int] = field(metadata=config(exclude=exclude_if_none), default=None)
    median_normal_width: Optional[int] = field(metadata=config(exclude=exclude_if_none), default=None)
    median_normal_length: Optional[int] = field(metadata=config(exclude=exclude_if_none), default=None)
    structure: Optional[Structure] = field(metadata=config(exclude=exclude_if_none), default=None)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class TextRegionAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    metadata: TextRegionMetadata
    begin_anchor: int
    end_anchor: int
    coords: List[List[int]]
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "TextRegion",
            "metadata": self.metadata.to_dict()
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class TextRegionAnnotation0:
    id: str
    label: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]
    iiif_url: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)

    def __post_init__(self):
        self.id = re.sub(r'-line-.*', '', self.id)

    def as_web_annotation(self) -> dict:
        body = classifying_body(as_urn(self.id), 'textregion')
        target = [resource_target(self.begin_anchor, self.end_anchor),
                  image_target(iiif_url=self.iiif_url, image_coords=self.image_coords)]
        for range in self.image_range:
            url = range[0]
            image_coords_list = range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


def to_image_coords(coords: List[List[int]]) -> ImageCoords:
    left = min([c[0] for c in coords])
    right = max([c[0] for c in coords])
    top = min([c[1] for c in coords])
    bottom = max([c[1] for c in coords])
    width = right - left
    height = bottom - top
    return ImageCoords(left=left, right=right, top=top, bottom=bottom, width=width, height=height)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class LineMetadata:
    id: str
    type: str
    parent_type: str
    parent_id: str
    scan_id: str
    page_id: str
    text_region_id: str
    column_id: str
    left_alignment: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    right_alignment: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    line_width: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class LineAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    metadata: LineMetadata
    begin_anchor: int
    end_anchor: int
    baseline: List[List[int]]
    coords: List[List[int]]
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Line",
            "metadata": self.metadata.to_dict()
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class LineAnnotation0:
    id: str
    label: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: ImageCoords
    iiif_url: Optional[str]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def as_web_annotation(self) -> dict:
        body = classifying_body(as_urn(self.id), 'line')
        target = [resource_target(self.begin_anchor, self.end_anchor),
                  image_target(iiif_url=self.iiif_url, image_coords=self.image_coords)]
        for i_range in self.image_range:
            url = i_range[0]
            image_coords_list = i_range[1]
            for ic in image_coords_list:
                target.append(image_target(url, ImageCoords.from_dict(ic)))
        for link in self.region_links:
            target.append(image_target(iiif_url=link))
        return web_annotation(body=body, target=target)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class SessionMetadata:
    id: str
    type: str
    date_shift_status: str
    has_session_date_element: bool
    index_timestamp: str
    inventory_num: int
    is_workday: bool
    lines_include_rest_day: bool
    resolution_ids: List[object]
    session_date: str
    session_day: int
    session_month: int
    session_num: int
    session_weekday: str
    session_year: int
    text_page_num: List[int]
    attendants_list_id: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    iiif_url: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    num_lines: Optional[int] = field(metadata=config(exclude=exclude_if_none), default=None)
    parent_id: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    parent_type: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    page_id: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    page_num: Optional[int] = field(metadata=config(exclude=exclude_if_none), default=None)
    president: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    scan_id: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)
    structure: Optional[Structure] = field(metadata=config(exclude=exclude_if_none), default=None)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class SessionAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    begin_anchor: int
    end_anchor: int
    evidence: List[Evidence]
    metadata: SessionMetadata
    provenance: Provenance
    region_links: List[str]
    coords: Optional[List[List[int]]] = field(metadata=config(exclude=exclude_if_none), default=None)

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Session",
            "metadata": self.metadata.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence]
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class SessionAnnotation0:
    id: str
    label: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    image_coords: Optional[ImageCoords]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]
    session_date: str
    session_year: int
    session_weekday: str
    president: Optional[str]

    def as_web_annotation(self) -> dict:
        body = [classifying_body(as_urn(self.id), 'session'),
                dataset_body({"date": self.session_date,
                              "year": self.session_year,
                              "weekday": self.session_weekday,
                              "president": self.president})]
        target = [resource_target(self.begin_anchor, self.end_anchor),
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
class AttendantsListMetadata:
    id: str
    type: str
    inventory_num: int
    source_id: str
    session_date: str
    session_id: str
    session_num: int
    session_year: int
    session_month: int
    session_day: int
    session_weekday: str
    text_page_num: List[int]
    index_timestamp: str
    president: Optional[str] = field(metadata=config(exclude=exclude_if_none), default=None)


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendanceSpan:
    offset: int
    end: int
    span_class: str = field(metadata=config(field_name="class"))
    pattern: str
    delegate_id: int
    delegate_name: str
    delegate_score: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantsListAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    begin_anchor: int
    end_anchor: int
    metadata: AttendantsListMetadata
    attendance_spans: List[AttendanceSpan]
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "AttendanceList",
            "metadata": self.metadata.to_dict(),
            "attendance_spans": [a.to_dict() for a in self.attendance_spans]
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantsListAnnotation0:
    id: str
    label: str
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
        target = [resource_target(self.begin_anchor, self.end_anchor)]
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
class AttendantMetadata:
    offset: int
    end: int
    metadata_class: str = field(metadata=config(field_name="class"))
    pattern: str
    delegate_id: int
    delegate_name: str
    delegate_score: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    metadata: AttendantMetadata
    begin_anchor: int
    end_anchor: int
    begin_char_offset: int
    end_char_offset: int
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Attendant",
            "metadata": self.metadata.to_dict()
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class AttendantAnnotation0:
    id: str
    label: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    metadata: Metadata
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    def as_web_annotation(self) -> dict:
        body = [classifying_body(as_urn(self.id), 'attendant'),
                dataset_body(self.metadata.to_dict())]
        target = [resource_target(self.begin_anchor, self.end_anchor)]
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
class ResolutionMetadata:
    id: str
    type: str
    structure: Structure
    parent_type: str
    parent_id: str
    scan_id: str
    page_id: str
    iiif_url: str
    page_num: int
    text_page_num: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ResolutionAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    begin_anchor: int
    end_anchor: int
    region_links: List[str]
    metadata: dict
    provenance: Provenance
    coords: Optional[List[List[int]]] = field(metadata=config(exclude=exclude_if_none), default=None)
    evidence: Optional[List[Evidence]] = field(metadata=config(exclude=exclude_if_none), default=None)

    def body(self) -> Dict[str, Any]:
        body = {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Resolution",
            "metadata": self.metadata
        }
        if self.evidence:
            body["evidence"] = [e.to_dict() for e in self.evidence]
        return body


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ResolutionAnnotation0:
    id: str
    label: str
    begin_anchor: int
    end_anchor: int
    resource_id: str
    proposition_type: Optional[str]
    image_range: List[List[Union[List[ImageCoords], str]]]
    region_links: List[str]

    # TODO: add proposition_type to body, image_range + region_links to target
    def as_web_annotation(self) -> dict:
        body = [classifying_body(as_urn(self.id), 'resolution')]
        if self.proposition_type:
            body.append({"proposition_type": self.proposition_type})
        target = [resource_target(self.begin_anchor, self.end_anchor)]
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
class RepublicParagraphMetadata:
    id: str
    type: str
    inventory_num: int
    source_id: str
    text_page_num: List[int]
    page_num: List[int]
    start_offset: int
    iiif_url: str
    doc_id: str
    lang: str
    paragraph_index: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class LineRange:
    start: int
    end: int
    line_id: str
    text_page_num: int
    page_num: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class RepublicParagraphAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    begin_anchor: int
    end_anchor: int
    metadata: RepublicParagraphMetadata
    line_ranges: List[LineRange]
    text: str
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "RepublicParagraph",
            "metadata": self.metadata.to_dict(),
            "text": self.text
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ReviewedMetadata:
    id: str
    type: str
    inventory_num: int
    source_id: str
    text_page_num: List[int]
    page_num: List[int]
    start_offset: int
    iiif_url: str
    doc_id: str
    lang: str
    paragraph_index: int


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ReviewedAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    begin_anchor: int
    end_anchor: int
    metadata: ReviewedMetadata
    line_ranges: List[LineRange]
    text: str
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Reviewed",
            "metadata": self.metadata.to_dict(),
            "text": self.text
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class PageMetadata:
    page_id: str
    scan_id: str


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class PageAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    begin_anchor: int
    end_anchor: int
    metadata: PageMetadata
    coords: List[List[int]]
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Page",
            "metadata": self.metadata.to_dict()
        }


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class ScanAnnotation(Annotation):
    id: str
    type: str
    resource_id: str
    iiif_url: str
    begin_anchor: int
    end_anchor: int
    region_links: List[str]
    provenance: Provenance

    def body(self) -> Dict[str, Any]:
        return {
            "@context": REPUBLIC_CONTEXT,
            "id": self.id,
            "type": "Scan"
        }


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
    return {
        "type": "Dataset",
        "value": metadata
    }


def resource_target(
        textrepo_base_url: str,
        version_id: str,
        begin_anchor: int,
        end_anchor: int,
        begin_char_offset: int = None,
        end_char_offset: int = None
) -> Dict[str, Any]:
    target = {
        "source": f"{textrepo_base_url}/rest/versions/{version_id}/contents",
        "type": "Text",
        "selector": {
            "type": as_urn("TextAnchorSelector"),
            "start": begin_anchor,
            "end": end_anchor
        }
    }
    if begin_char_offset is not None:
        target["selector"]["begin_char_offset"] = begin_char_offset
        target["selector"]["end_char_offset"] = end_char_offset
    return target


def selection_view_target(
        textrepo_base_url: str,
        version_id: str,
        begin_anchor: int,
        end_anchor: int,
        begin_char_offset: int = None,
        end_char_offset: int = None
) -> Dict[str, Any]:
    if begin_char_offset is not None:
        coord_params = f"{begin_anchor}/{begin_char_offset}/{end_anchor}/{end_char_offset}"
    else:
        coord_params = f"{begin_anchor}/{end_anchor}"
    return {
        "source": f"{textrepo_base_url}/view/versions/{version_id}/segments/index/{coord_params}",
        "type": "Text"
    }


def image_target(iiif_url: str = "https://example.org/missing-iiif-url",
                 image_coords: ImageCoords = None,
                 scan_id: str = None) -> dict:
    target = {
        "source": iiif_url,
        "type": "Image"
    }
    if image_coords:
        xywh = f"{image_coords.left},{image_coords.top},{image_coords.width},{image_coords.height}"
        target['selector'] = {
            "type": "FragmentSelector",
            "conformsTo": "http://www.w3.org/TR/media-frags/",
            "value": f"xywh={xywh}"
        }
    if scan_id:
        target['id'] = scan_id
    return target


def image_target_wth_svg_selector(iiif_url: str,
                                  coords: List,
                                  scan_id: str = None) -> dict:
    target = {
        "source": iiif_url,
        "type": "Image"
    }
    points = ' '.join([f"{c[0]},{c[1]}" for c in coords])
    height = max([c[1] for c in coords])
    width = max([c[0] for c in coords])
    polygon = f"""<polygon points="{points}"/>"""
    path_def = ' '.join([f"L{c[0]} {c[1]}" for c in coords]) + " Z"
    path_def = 'M' + path_def[1:]
    path = f"""<path d="{path_def}"/>"""
    target['selector'] = {
        "type": "SvgSelector",
        "value": f"""<svg height="{height}" width="{width}">{path}</svg>"""
    }
    if scan_id:
        target['id'] = scan_id
    return target


def recursively_get_fields(d: dict) -> Set[str]:
    fields = set()
    for (key, value) in d.items():
        fields.add(key)
        if isinstance(value, Dict):
            fields = fields.union(recursively_get_fields(value))
    return fields


def get_custom_fields(body, target, custom) -> Set[str]:
    fields = set()
    for part in [body, target, custom]:
        if isinstance(part, dict):
            fields = fields.union(recursively_get_fields(part))
        if isinstance(part, list):
            for d in part:
                fields = fields.union(recursively_get_fields(d))
    return fields.difference(anno_context_fields)


custom_context_prefix = "http://example.org/customwebannotationfield#"


def create_context(custom_fields: Set[str]) -> Dict[str, str]:
    return {f: f"{custom_context_prefix}{f}" for f in custom_fields}


def web_annotation(body: Any,
                   target: Any,
                   anno_id: uri = None,
                   provenance: Provenance = None,
                   custom: dict = None) -> dict:
    if not anno_id:
        anno_id = f"urn:republic:annotation:{uuid.uuid4()}"
    contexts = [
        "http://www.w3.org/ns/anno.jsonld",
        {"provenance": "https://humanities.knaw.nl/ns/provenance#hasProvenance"}
    ]

    context = contexts[0] if len(contexts) == 1 else contexts
    annotation = {
        "@context": context,
        "id": anno_id,
        "type": "Annotation",
        "motivation": "classifying",
        "generated": datetime.today().isoformat(),
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
    if provenance:
        annotation["provenance"] = provenance.to_dict()
        annotation["provenance"]["@context"] = "https://brambg.github.io/ns/provenance.jsonld"

    # ic(annotation)
    camel_cased = keys_to_camel_case(annotation)
    return force_iri_values(camel_cased,
                            {"id", "docId", "lineId", "parentId", "pageId", "resourceId", "scanId", "sessionId",
                             "textRegionId", "columnId", "sourceId", "textId"},
                            "urn:republic:")


def classifying_annotation_mapper(annotation: dict, value: str) -> dict:
    body = {
        "type": "TextualBody",
        "purpose": "classifying",
        "value": value
    }
    anno_id = annotation.pop('id', None)
    if anno_id:
        body['id'] = anno_id
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
        target = {
            "source": iiif_url,
            "type": "Image",
            "selector": {
                "type": "FragmentSelector",
                "conformsTo": "http://www.w3.org/TR/media-frags/",
                "value": f"xywh={xywh}"
            }
        }
        if scan_id:
            target['id'] = scan_id
        targets.append(target)
    elif scan_id:
        iiif_url = annotation.pop('iiif_url')
        target = {
            "id": scan_id,
            "source": iiif_url,
            "type": "Image",
        }
        targets.append(target)

    target = targets if len(targets) > 1 else targets[0]
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
        "target": target
    }
    if annotation:
        web_annotation["_unused_fields_from_original"] = annotation
    return web_annotation


def as_urn(id: str) -> str:
    return f"urn:republic:{id}"


def get_anno_context_fields():
    anno_context = requests.get('http://www.w3.org/ns/anno.jsonld').json()
    return set(anno_context['@context'].keys())


anno_context_fields = get_anno_context_fields()


def is_iri(value: str) -> bool:
    try:
        parse(value, rule='IRI')
        return True
    except ValueError:
        return False


def as_iri(value: str, prefix: str):
    if is_iri(value):
        return value
    else:
        return f"{prefix}{value}"


def force_iri_values_in_list(l: List, id_fields: Set[str], prefix: str) -> List:
    new_list = []
    for e in l:
        if isinstance(e, dict):
            new_list.append(force_iri_values(e, id_fields, prefix))
        elif isinstance(e, list):
            new_list.append(force_iri_values_in_list(e, id_fields, prefix))
        else:
            new_list.append(e)
    return new_list


def force_iri_values(d: dict, id_fields: Set[str], prefix: str) -> dict:
    for (k, v) in d.items():
        if k in id_fields:
            d[k] = as_iri(v, prefix)
        elif isinstance(v, dict):
            d[k] = force_iri_values(v, id_fields, prefix)
        elif isinstance(v, list):
            d[k] = force_iri_values_in_list(v, id_fields, prefix)
    return d
