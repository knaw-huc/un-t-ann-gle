from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


@dataclass
class TFAnnotation:
    id: str
    type: str
    body: str
    target: str


@dataclass
class IAnnotation:
    id: str = ""
    type: str = ""
    tf_node: int = 0
    text: str = ""
    start_anchor: int = 0
    end_anchor: int = 0
    metadata: Dict[str, any] = field(default_factory=dict)


tt_types = ("page", "folder", "letter", "sentence")


def as_class_name(string: str) -> str:
    return string[0].capitalize() + string[1:]


@dataclass
class AnnotationTransformer:
    textrepo_url: str
    textrepo_version: str

    def as_web_annotation(self, ia: IAnnotation) -> Dict[str, Any]:
        if ia.type in tt_types:
            body_type = f"{as_class_name(ia.type)}"
        else:
            body_type = f"tei:{as_class_name(ia.type)}"
        anno = {
            "@context": [
                "http://www.w3.org/ns/anno.jsonld",
                {
                    "tt": "https://ns.tt.di.huc.knaw.nl/tt",
                    "tei": "https://ns.tt.di.huc.knaw.nl/tei"
                }
            ],
            "type": "Annotation",
            "purpose": "tagging",
            "generated": datetime.today().isoformat(),
            "body": {
                "id": f"urn:mondriaan:{ia.type}:{ia.tf_node}",
                "type": body_type,
                "tt:textfabric_node": ia.tf_node,
                "text": ia.text
            },
            "target": [
                {
                    "source": f"{self.textrepo_url}/rest/versions/{self.textrepo_version}/contents",
                    "type": "Text",
                    "selector": {
                        "type": "tt:TextAnchorSelector",
                        "start": ia.start_anchor,
                        "end": ia.end_anchor
                    }
                },
                {
                    "source": (
                        f"{self.textrepo_url}/view/versions/{self.textrepo_version}/segments/index/{ia.start_anchor}/{ia.end_anchor}"),
                    "type": "Text"
                }
            ]
        }
        if ia.metadata:
            anno["body"]["metadata"] = {f"{k}": v for k, v in ia.metadata.items()}
        if ia.type == "letter":
            anno["body"]["metadata"]["folder"] = "proeftuin"
            anno["target"].append({
                "source": "https://images.diginfra.net/iiif/NL-HaNA_1.01.02%2F3783%2FNL-HaNA_1.01.02_3783_0002.jpg/full/full/0/default.jpg",
                "type": "Image"
            })
        if ia.type == "folder":
            anno["body"]["metadata"]["manifest"] = \
                "https://images.diginfra.net/api/pim/imageset/67533019-4ca0-4b08-b87e-fd5590e7a077/manifest"
            anno["body"].pop("text")
        else:
            canvas_target = {
                "@context": "https://brambg.github.io/ns/republic.jsonld",
                "source": "https://images.diginfra.net/api/pim/iiif/67533019-4ca0-4b08-b87e-fd5590e7a077/canvas/20633ef4-27af-4b13-9ffe-dfc0f9dad1d7",
                "type": "Canvas"
            }
            anno["target"].append(canvas_target)
        return anno
