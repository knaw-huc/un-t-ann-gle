from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class TFAnnotation:
    id: int
    target: str
    type: str
    body: str


@dataclass
class IAnnotation:
    id: int = 0
    type: str = ""
    tf_node: int = 0
    text: str = ""
    start_anchor: int = 0
    end_anchor: int = 0
    metadata: Dict[str, any] = field(default_factory=dict)


def as_web_annotation(ia: IAnnotation):
    textrepo_url = "https://mondriaan-textrepo.tt.di.huc.knaw.nl"
    textrepo_version = "42df1275-81cd-489c-b28c-345780c3889b"
    return {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "type": "Annotation",
        "generated": datetime.today().isoformat(),
        "body": {
            "type": f"m:{ia.type.capitalize()}",
            "id": f"urn:mondriaan:{ia.type}:{ia.tf_node}",
            "m:textfabric_node": ia.tf_node,
            "text": ia.text,
            "metadata": ia.metadata
        },
        "target": [
            {
                "source": f"{textrepo_url}/api/rest/versions/{textrepo_version}/contents",
                "type": "Text",
                "selector": {
                    "@context": "https://brambg.github.io/ns/republic.jsonld",
                    "type": "urn:republic:TextAnchorSelector",
                    "start": ia.start_anchor,
                    "end": ia.end_anchor
                }
            },
            {
                "source": (
                    f"{textrepo_url}/api/view/versions/{textrepo_version}/segments/index/{ia.start_anchor}/{ia.end_anchor}"),
                "type": "Text"
            }
        ]
    }