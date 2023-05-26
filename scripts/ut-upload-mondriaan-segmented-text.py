#!/usr/bin/env python3
from textrepo.client import TextRepoClient


def main():
    basedir = 'data'
    tf_text_file = f"{basedir}/mondriaan-text.json"
    trc = TextRepoClient("https://mondriaan.tt.di.huc.knaw.nl/textrepo", verbose=True)
    # external_id = "mondriaan-letters"
    # trc.purge_document(external_id)
    # doc_id = trc.create_document(external_id)
    # print(f"doc_id={doc_id}")
    # file_id = trc.create_document_file(doc_id, 1)
    # print(f"file_id={file_id}")
    file_id = "52086574-0c84-4ea0-b77b-ef11b6214252"
    with open(tf_text_file) as f:
        content = f.read()
    version_id = trc.create_version(file_id=file_id, file=content)
    print(f"version_id={version_id}")


if __name__ == '__main__':
    main()
