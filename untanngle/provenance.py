from dataclasses import dataclass
from datetime import datetime
from typing import Union, List, Dict, Any

import requests
from loguru import logger
from uri import URI


@dataclass
class ProvenanceHow:
    software: URI
    init: Union[str, None] = None
    delta: Union[str, None] = None


@dataclass
class ProvenanceWhy:
    motivation: Union[str, None] = None
    provenance_schema: Union[str, None] = None


@dataclass
class ProvenanceResource:
    resource: URI
    relation: str


@dataclass
class ProvenanceData:
    sources: List[ProvenanceResource]
    targets: List[ProvenanceResource]
    who: URI
    where: URI
    when: Union[datetime, str]
    how: ProvenanceHow
    why: ProvenanceWhy

    def to_dict(self) -> Dict[str, Any]:
        _dict = {}
        if self.who:
            _dict['who'] = str(self.who)
        if self.when:
            if type(self.when) == datetime:
                _dict['when'] = self.when.astimezone().replace(microsecond=0).isoformat()
            else:
                _dict['when'] = str(self.when)
        if self.where:
            _dict['where'] = str(self.where)
        if self.how:
            if self.how.software:
                _dict['how_software'] = str(self.how.software)
            if self.how.init:
                _dict['how_init'] = str(self.how.init)
            if self.how.delta:
                _dict['how_delta'] = str(self.how.delta)
        if self.why:
            if self.why.motivation:
                _dict['why_motivation'] = str(self.why.motivation)
            if self.why.provenance_schema:
                _dict['why_provenance_schema'] = str(self.why.provenance_schema)
        _dict['source'] = [str(s.resource) for s in self.sources]
        _dict['source_rel'] = [str(s.relation) for s in self.sources]
        _dict['target'] = [str(t.resource) for t in self.targets]
        _dict['target_rel'] = [str(t.relation) for t in self.targets]
        return _dict


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
        if not response.ok:
            logger.error(f"response={response}")
            raise Exception(f"server returned error: {response.text}")
        prov_id = response.headers['Location'][1:]
        return prov_id
