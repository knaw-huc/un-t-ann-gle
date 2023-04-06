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


def as_web_annotation(ia: IAnnotation, textrepo_url: str, textrepo_version: str) -> Dict[str, Any]:
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
            "type": f"tei:{ia.type.capitalize()}",
            "tt:textfabric_node": ia.tf_node,
            "text": ia.text
        },
        "target": [
            {
                "source": f"{textrepo_url}/rest/versions/{textrepo_version}/contents",
                "type": "Text",
                "selector": {
                    "type": "tt:TextAnchorSelector",
                    "start": ia.start_anchor,
                    "end": ia.end_anchor
                }
            },
            {
                "source": (
                    f"{textrepo_url}/view/versions/{textrepo_version}/segments/index/{ia.start_anchor}/{ia.end_anchor}"),
                "type": "Text"
            }
        ]
    }
    if ia.metadata:
        anno["body"]["tt:metadata"] = {f"tei:{k}": v for k, v in ia.metadata.items()}
    return anno
