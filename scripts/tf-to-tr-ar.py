#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from itertools import zip_longest
from typing import List, Any

import requests
from annorepo.client import AnnoRepoClient
from github import Github
from icecream import ic
from loguru import logger
from textrepo.client import TextRepoClient
from uri import URI

from untanngle import mondriaan
from untanngle.provenance import ProvenanceClient, ProvenanceData, ProvenanceHow, ProvenanceWhy, ProvenanceResource


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Download the given version of the TF watm export, process it and"
                    " upload it to the given TextRepo and AnnoRepo servers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v",
                        "--version",
                        required=True,
                        help="The version of the TF watm export to use",
                        type=str)
    args = parser.parse_args()
    process(args.version)


textrepo_base_uri = "https://mondriaan.tt.di.huc.knaw.nl/textrepo"
textrepo_file_id = "52086574-0c84-4ea0-b77b-ef11b6214252"
textrepo_external_id = "mondriaan-letters"
annorepo_base_uri = "https://annorepo.tt.di.huc.knaw.nl"
annorepo_api_key = "9ac93a6a-277a-42f1-bd38-c38ea8ac3c45"
annorepo_container_id = "mondriaan-letters"
annorepo_container_label = "mondriaan-letters"
provenance_base_uri = "http://localhost:8080"
provenance_api_key = "7c7f89e7-5ce4-4b79-b475-538d5f9ddad0"


def upload_to_tr(tf_text_file: str) -> str:
    trc = TextRepoClient(textrepo_base_uri, verbose=True)
    # trc.purge_document(external_id)
    # doc_id = trc.create_document(external_id)
    # print(f"doc_id={doc_id}")
    # file_id = trc.create_document_file(doc_id, 1)
    # print(f"file_id={file_id}")
    with open(tf_text_file) as f:
        content = f.read()
    version_id = trc.import_version(external_id=textrepo_external_id,
                                    type_name='segmented_text',
                                    contents=content,
                                    as_latest_version=True)
    return version_id.version_id


def create_web_annotations(anno_file: str, text_file: str, tr_version_id: str) -> str:
    logger.info(f"converting {anno_file}")
    web_annotations = mondriaan.convert(anno_file=anno_file,
                                        text_file=text_file,
                                        textrepo_url=textrepo_base_uri,
                                        textrepo_file_version=tr_version_id)
    annotations_json = "out/mondriaan-web-annotations.json"
    logger.info(f"writing {annotations_json}")
    with open(annotations_json, "w") as f:
        json.dump(web_annotations, fp=f, indent=2)
    return annotations_json


def permalink(repo_name: str, path: str) -> str | None:
    access_token = os.environ.get('GITHUB_ACCESS_TOKEN')
    g = Github(access_token)

    repo = g.get_repo(repo_name)
    commits = repo.get_commits(path=path)

    if commits.totalCount > 0:
        commit_sha = commits[0].sha
        return f"https://github.com/{repo_name}/raw/{commit_sha}/{path}"
    else:
        logger.error(f"No commits found for {path}.")
        return None


def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
    return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]


def upload_to_ar(webanno_file: str) -> str:
    ar = AnnoRepoClient(annorepo_base_uri, verbose=False, api_key=annorepo_api_key)

    if not ar.has_container(annorepo_container_id):
        logger.info(f"container {annorepo_base_uri}/w3c/{annorepo_container_id} not found, creating...")
        ar.create_container(name=annorepo_container_id, label=annorepo_container_label)

    logger.info(f"reading {webanno_file}...")
    with open(webanno_file) as f:
        annotation_list = json.load(f)
    number_of_annotations = len(annotation_list)

    logger.info(f"{number_of_annotations} annotations found.")

    chunk_size = 150
    chunked_annotations = chunk_list(annotation_list, chunk_size)
    number_of_chunks = len(chunked_annotations)
    container_uri = f"{annorepo_base_uri}/w3c/{annorepo_container_id}"
    logger.info(
        f"uploading {number_of_annotations} annotations to {container_uri}"
        f" in {number_of_chunks} chunks of at most {chunk_size} annotations ...")
    for i, chunk in enumerate(chunked_annotations):
        print(f"chunk ({i + 1}/{number_of_chunks})", end='\r')
        annotation_ids = ar.add_annotations(annorepo_container_id, chunk)
    logger.info("done!")
    return container_uri


def process(watm_version: str):
    # download text.json
    # upload to tr; save version id
    # use version id when converting anno.json to web annotations
    # upload web-anno to ar
    # upload provenance:
    #   tf text.json url-> tr version url
    #   tf anno.json url -> ar container url

    # config.yml with:
    #     watm version
    #     tr url
    #     ar url
    #     container name

    text_permalink = permalink(repo_name="annotation/mondriaan", path=f"watm/{watm_version}/text.json")
    text_file = 'data/watm/mondriaan-text.json'
    download_file(text_permalink, text_file)

    tr_version_id = upload_to_tr(text_file)
    ic(tr_version_id)
    text_target_uri = f"https://mondriaan.tt.di.huc.knaw.nl/textrepo/rest/versions/{tr_version_id}"
    pc = ProvenanceClient(provenance_base_uri, provenance_api_key)
    textprov_location = post_provenance(provenance_client=pc,
                                        source=text_permalink, target=text_target_uri,
                                        motivation='Installing')

    anno_permalink = permalink(repo_name="annotation/mondriaan", path=f"watm/{watm_version}/anno.json")
    anno_file = 'data/watm/mondriaan-anno.json'
    download_file(anno_permalink, anno_file)

    webanno_file = create_web_annotations(anno_file=anno_file, text_file=text_file, tr_version_id=tr_version_id)
    container_uri = upload_to_ar(webanno_file)
    annoprov_location = post_provenance(provenance_client=pc,
                                        source=anno_permalink, target=container_uri,
                                        motivation='Converting')

    print(f"textrepo: {text_target_uri}")
    print(f"provenance: {textprov_location}")
    print(f"annorepo: {container_uri}")
    print(f"provenance: {annoprov_location}")


def post_provenance(provenance_client: ProvenanceClient, source: str, target: str, motivation: str) -> URI:
    tr_provenance = ProvenanceData(
        who=URI('orcid:0000-0002-3755-5929'),
        where=URI('https://di.huc.knaw.nl/'),
        when=datetime.now(),
        how=ProvenanceHow(
            software=URI('https://github.com/knaw-huc/un-t-ann-gle/blob/tt-878-republic-annotaties-omzetten/'
                         'scripts/tf-to-tr-ar.py'),
            init=''),
        why=ProvenanceWhy(motivation=motivation),
        sources=[ProvenanceResource(resource=URI(source), relation='primary')],
        targets=[ProvenanceResource(resource=URI(target), relation='primary')],
    )
    provenance_id = provenance_client.add_provenance(tr_provenance)
    logger.info(f"provenance location: {provenance_id.location}")
    return provenance_id.location


def download_file(source_uri, target_path):
    logger.info(f"reading {source_uri}")
    response = requests.get(source_uri)
    text = response.text
    logger.info(f"writing {target_path}")
    with open(target_path, 'w') as f:
        f.write(text)


if __name__ == '__main__':
    main()
