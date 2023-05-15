from dataclasses import dataclass
from typing import Union, List

import requests
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class ProvenanceData:
    who: str
    where: str
    when: str
    how_software: str
    how_init: str
    why: str
    source: Union[str, List[str]]
    source_rel: Union[str, List[str]]
    target: Union[str, List[str]]
    target_rel: Union[str, List[str]]


class ProvenanceClient:

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def add_provenance(self, provenance_data: ProvenanceData) -> str:
        response = requests.post(
            f'{self.base_url}/prov',
            data=provenance_data.to_dict(),
            headers={'Authorization': f'Basic: {self.api_key}'}
        )
        prov_id = response.headers['Location'][1:]
        return prov_id
