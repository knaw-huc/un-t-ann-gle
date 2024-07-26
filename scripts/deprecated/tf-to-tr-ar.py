#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from itertools import zip_longest
from typing import List, Any

import requests
import yaml
from annorepo.client import AnnoRepoClient
from github import Github
from loguru import logger
from provenance.client import ProvenanceClient, ProvenanceData, ProvenanceHow, ProvenanceWhy, ProvenanceResource
from textrepo.client import TextRepoClient
from uri import URI

from untanngle import textfabric

## deprecated; use ut-convert-*.py scripts

@dataclass
class Config:
    config_path: str
    textfabric_watm_version: str
    textrepo_base_uri: str
    textrepo_external_id: str
    annorepo_base_uri: str
    annorepo_api_key: str
    annorepo_container_id: str
    annorepo_container_label: str
    provenance_base_uri: str
    provenance_api_key: str
    provenance_who: str
    provenance_where: str
    text_in_annotation_body: bool


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Download the given version of the TF watm export, process it and"
                    " upload it to the given TextRepo and AnnoRepo servers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("config_file", type=str, help="the configuration file (yaml)")
    args = parser.parse_args()
    config = load_config(args.config_file)
    WatmProcessor(config).run()


def load_config(conf_path: str) -> Config:
    logger.info(f"reading config from {conf_path}")
    with open(conf_path, "r") as f:
        config = yaml.safe_load(f)
    return Config(
        config_path=conf_path,
        textfabric_watm_version=config['textfabric']['watm_version'],
        textrepo_base_uri=config['textrepo']['base_uri'].rstrip('/'),
        textrepo_external_id=config['textrepo']['external_id'],
        annorepo_base_uri=config['annorepo']['base_uri'].rstrip('/'),
        annorepo_api_key=config['annorepo']['api_key'],
        annorepo_container_id=config['annorepo']['container_id'],
        annorepo_container_label=config['annorepo']['container_label'],
        provenance_base_uri=config['provenance']['base_uri'],
        provenance_api_key=config['provenance']['api_key'],
        provenance_who=config['provenance']['who'],
        provenance_where=config['provenance']['where'],
        text_in_annotation_body=config['text_in_annotation_body']
    )


class WatmProcessor:

    def __init__(self, config: Config):
        self.config = config

    def run(self):
        text_permalink = self.permalink(repo_name="annotation/mondriaan",
                                        path=f"watm/{self.config.textfabric_watm_version}/text.json")
        text_file = 'data/watm/mondriaan-text.json'
        self.download_file(text_permalink, text_file)

        tr_version_id = self.upload_to_tr(text_file)
        # ic(tr_version_id)
        text_target_uri = f"https://mondriaan.tt.di.huc.knaw.nl/textrepo/rest/versions/{tr_version_id}"
        pc = ProvenanceClient(self.config.provenance_base_uri, self.config.provenance_api_key)
        textprov_location = self.post_provenance(provenance_client=pc,
                                                 source=text_permalink, target=text_target_uri,
                                                 motivation='Installing')

        anno_permalink = self.permalink(repo_name="annotation/mondriaan",
                                        path=f"watm/{self.config.textfabric_watm_version}/anno.json")
        anno_file = 'data/watm/mondriaan-anno.json'
        self.download_file(anno_permalink, anno_file)

        webanno_file = self.create_web_annotations(anno_file=anno_file, text_file=text_file,
                                                   tr_version_id=tr_version_id)
        container_uri = self.upload_to_ar(webanno_file)
        annoprov_location = self.post_provenance(provenance_client=pc,
                                                 source=anno_permalink, target=container_uri,
                                                 motivation='Converting')

        print(f"textrepo: {text_target_uri}")
        print(f"provenance: {textprov_location}")
        print(f"annorepo: {container_uri}")
        print(f"provenance: {annoprov_location}")

    def upload_to_tr(self, tf_text_file: str) -> str:
        trc = TextRepoClient(self.config.textrepo_base_uri, verbose=True)
        with open(tf_text_file) as f:
            content = f.read()
        version_id = trc.import_version(external_id=self.config.textrepo_external_id,
                                        type_name='segmented_text',
                                        contents=content,
                                        as_latest_version=True)
        return version_id.version_id

    def create_web_annotations(self, anno_file: str, text_file: str, tr_version_id: str) -> str:
        logger.info(f"converting {anno_file}")
        web_annotations = textfabric.convert(project='mondriaan', anno_files=[anno_file], text_files=text_file,
                                             anno2node_path=anno2node_path, textrepo_url=self.config.textrepo_base_uri,
                                             textrepo_file_versions=tr_version_id,
                                             text_in_body=self.config.text_in_annotation_body)
        annotations_json = "out/mondriaan-web-annotations.json"
        logger.info(f"writing {annotations_json}")
        with open(annotations_json, "w") as f:
            json.dump(web_annotations, fp=f, indent=2)
        return annotations_json

    @staticmethod
    def permalink(repo_name: str, path: str) -> str | None:
        access_token = os.environ.get('GITHUB_ACCESS_TOKEN')
        g = Github(access_token)

        repo = g.get_repo(repo_name)
        commits = repo.get_commits(path=path)

        if commits.totalCount > 0:
            commit_sha = commits[0].sha
            return f"https://raw.githubusercontent.com/{repo_name}/{commit_sha}/{path}"
        else:
            logger.error(f"No commits found for {path}.")
            return None

    @staticmethod
    def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
        return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]

    def upload_to_ar(self, webanno_file: str) -> str:
        ar = AnnoRepoClient(self.config.annorepo_base_uri, verbose=False, api_key=self.config.annorepo_api_key)

        if not ar.has_container(self.config.annorepo_container_id):
            logger.info(
                f"container {self.config.annorepo_base_uri}/w3c/{self.config.annorepo_container_id} not found, creating...")
            ar.create_container(name=self.config.annorepo_container_id, label=self.config.annorepo_container_label)

        logger.info(f"reading {webanno_file}...")
        with open(webanno_file) as f:
            annotation_list = json.load(f)
        number_of_annotations = len(annotation_list)

        logger.info(f"{number_of_annotations} annotations found.")

        chunk_size = 150
        chunked_annotations = self.chunk_list(annotation_list, chunk_size)
        number_of_chunks = len(chunked_annotations)
        container_uri = f"{self.config.annorepo_base_uri}/w3c/{self.config.annorepo_container_id}"
        logger.info(
            f"uploading {number_of_annotations} annotations to {container_uri}"
            f" in {number_of_chunks} chunks of at most {chunk_size} annotations ...")
        for i, chunk in enumerate(chunked_annotations):
            print(f"chunk ({i + 1}/{number_of_chunks})", end='\r')
            annotation_ids = ar.add_annotations(self.config.annorepo_container_id, chunk)
        logger.info("done!")
        return container_uri

    def post_provenance(self, provenance_client: ProvenanceClient, source: str, target: str, motivation: str) -> URI:
        commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        tr_provenance = ProvenanceData(
            who=URI(self.config.provenance_who),
            where=URI(self.config.provenance_where),
            when=datetime.now(),
            how=ProvenanceHow(
                software=URI(
                    f'https://raw.githubusercontent.com/knaw-huc/un-t-ann-gle/{commit_id}/scripts/tf-to-tr-ar.py'),
                init=f'{self.config.config_path}'),
            why=ProvenanceWhy(motivation=motivation),
            sources=[ProvenanceResource(resource=URI(source), relation='primary')],
            targets=[ProvenanceResource(resource=URI(target), relation='primary')],
        )

        provenance_id = provenance_client.add_provenance(tr_provenance)
        logger.info(f"provenance location: {provenance_id.location}")
        return provenance_id.location

    @staticmethod
    def download_file(source_uri, target_path):
        logger.info(f"reading {source_uri}")
        response = requests.get(source_uri)
        text = response.text
        logger.info(f"writing {target_path}")
        with open(target_path, 'w') as f:
            f.write(text)


if __name__ == '__main__':
    main()
