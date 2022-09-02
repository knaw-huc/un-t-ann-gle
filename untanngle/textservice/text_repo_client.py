import uuid
from typing import Optional

import requests


class TextRepoClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_types(self) -> dict:
        response = requests.get(url=f'{self.base_url}/rest/types')
        type_list = response.json()
        return {t['id']: t['name'] for t in type_list}

    def create_document(self, external_id: str) -> uuid:
        response = requests.post(url=self.base_url + "/rest/documents",
                                 json={"externalId": external_id})
        # pprint(response)
        return response.json()['id']

    def create_file(self, document_id: uuid, type_id: int) -> uuid:
        response = requests.post(url=self.base_url + "/rest/files",
                                 json={"docId": document_id, "typeId": type_id})
        # pprint(response)
        return response.json()['id']

    def create_version(self, file_id: uuid, contents: str) -> uuid:
        response = requests.post(url=self.base_url + "/rest/versions",
                                 files={"fileId": file_id, "contents": contents})
        # pprint(response)
        return response.json()['id']

    def get_type_id(self, name: str) -> Optional[int]:
        type_dict = self.get_types()
        for k, v in type_dict.items():
            if v == name:
                return k
        return None

    def purge_document_by_external_id(self, external_id):
        response = requests.delete(url=self.base_url + "/task/delete/documents/" + external_id)
        # pprint(response)
