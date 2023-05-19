#!/usr/bin/env python3
import argparse
import json
import os

import requests
from github import Github
from icecream import ic
from loguru import logger
from textrepo.client import TextRepoClient

from untanngle import mondriaan


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
    # text_source_uri = f"https://raw.githubusercontent.com/annotation/mondriaan/master/watm/{watm_version}/text.json"
    text_file = 'data/watm/mondriaan-text.json'
    download_file(text_permalink, text_file)

    tr_version_id = upload_to_tr(text_file)
    ic(tr_version_id)
    text_target_uri = f"https://mondriaan.tt.di.huc.knaw.nl/textrepo/rest/versions/{tr_version_id}"

    anno_permalink = permalink(repo_name="annotation/mondriaan", path=f"watm/{watm_version}/anno.json")
    # anno_source_uri = f"https://raw.githubusercontent.com/annotation/mondriaan/master/watm/{watm_version}/anno.json"
    anno_file = 'data/watm/mondriaan-anno.json'
    download_file(anno_permalink, anno_file)

    webanno_file = create_web_annotations(anno_file=anno_file, text_file=text_file, tr_version_id=tr_version_id)


def download_file(source_uri, target_path):
    logger.info(f"reading {source_uri}")
    response = requests.get(source_uri)
    text = response.text
    logger.info(f"writing {target_path}")
    with open(target_path, 'w') as f:
        f.write(text)


if __name__ == '__main__':
    main()
