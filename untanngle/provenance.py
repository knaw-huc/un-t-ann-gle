from dataclasses import dataclass
from datetime import datetime
from typing import Union, List, Dict, Any

import requests
from icecream import ic
from loguru import logger
from uri import URI


@dataclass
class ProvenanceIdentifier:
    id: str
    location: URI


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


def log_curl_command(authorization, data, url):
    ic(data)
    data_params = []
    for k, v in data.items():
        if type(v) == list:
            for sub_v in v:
                data_params.append(f"-d \"{k}={sub_v}\"")
        else:
            data_params.append(f"-d \"{k}={v}\"")

    data_param_str = " ".join(data_params)
    logger.debug(f"curlie -i -X POST -H 'Authorization: {authorization}' "
                 f"{data_param_str} {url}")


class ProvenanceClient:

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers = {'Authorization': f'Basic: {api_key}'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # logger.debug(f"closing session with args: {args}")
        self.session.close()

    def close(self):
        self.__exit__()

    def add_provenance(self, provenance_data: ProvenanceData) -> ProvenanceIdentifier:
        url = f'{self.base_url}/prov'
        data = provenance_data.to_dict()
        # log_curl_command(authorization, data, url)
        response = requests.post(
            url=url,
            data=data
        )
        # ic(response.request.headers)
        # ic(response.headers)
        if not response.ok:
            logger.error(f"response={response}")
            raise Exception(f"server returned error: {response.text}")
        prov_id = response.headers['Location'][1:]
        return ProvenanceIdentifier(id=prov_id, location=URI(f"{self.base_url}/prov/{prov_id}"))
