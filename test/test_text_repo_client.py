import uuid
from pprint import pprint
from unittest import TestCase

from textservice.text_repo_client import TextRepoClient


class TestTextRepoClient(TestCase):
    global client, base_url
    base_url = "https://demorepo.tt.di.huc.knaw.nl/api"
    client = TextRepoClient(base_url)

    def test_get_types(self):
        files = client.get_types()
        pprint(files)

    def test_create_version(self):
        external_id = 'test_document'
        client.purge_document_by_external_id(external_id=external_id)
        document_id = client.create_document(external_id)
        self.print_document_uris(document_id)

        type_id = 40  # client.get_type_id('plaintext')
        file_id = client.create_file(document_id, type_id)
        self.print_file_uris(file_id)

        contents = 'Hello World\nbla\nbla\nbla\nGoodbye World!'
        version_id = client.create_version(file_id, contents)
        self.print_version_uris(version_id)

    def print_document_uris(self, document_id: uuid):
        print(f'{base_url}/rest/documents/{document_id}')
        print(f'{base_url}/rest/documents/{document_id}/files')

    def print_file_uris(self, file_id: uuid):
        print(f'{base_url}/rest/files/{file_id}')
        print(f'{base_url}/rest/files/{file_id}/versions')

    def print_version_uris(self, version_id: uuid):
        print(f'{base_url}/rest/versions/{version_id}')
        print(f'{base_url}/rest/versions/{version_id}/contents')
