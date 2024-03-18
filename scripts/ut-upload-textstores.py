#!/usr/bin/env python3

import argparse
import glob
import subprocess
from datetime import datetime
from os.path import exists
from typing import List

from loguru import logger
from provenance.client import ProvenanceClient, ProvenanceData, ProvenanceHow, ProvenanceWhy, ProvenanceResource
from textrepo.client import TextRepoClient
from uri import URI

from untanngle.utils import trim_trailing_slash, add_segmented_text_type_if_missing, read_json, write_json

version_id_idx_path = "out/version_id_idx.json"


def get_session_files(sessions_folder: str) -> List[str]:
    path = f"{sessions_folder}/session-*-num*.json"
    session_file_names = (f for f in glob.glob(path))
    return sorted(session_file_names)


def store_provenance(textrepo_version_url: str,
                     session_files_path: str,
                     year: int,
                     provenance_url: str,
                     provenance_api_key: str):
    commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    pc = ProvenanceClient(provenance_url, provenance_api_key)
    session_files = get_session_files(session_files_path)
    session_urls = [
        f"https://annotation.republic-caf.diginfra.org/elasticsearch/session_lines/_doc/{f.replace(f'{session_files_path}/', '').replace('.json', '')}"
        for f in session_files]
    prov_data = ProvenanceData(
        who=URI("orcid:0000-0002-3755-5929"),
        where=URI("file://LAP1550/"),
        when=datetime.now(),
        how=ProvenanceHow(
            software=URI(
                f'https://raw.githubusercontent.com/knaw-huc/un-t-ann-gle/{commit_id}/scripts/ut-run-republic-pipeline-for-year.sh'),
            init=str(year)),
        why=ProvenanceWhy(motivation="text extraction"),
        sources=[ProvenanceResource(resource=URI(u), relation='primary') for u in session_urls],
        targets=[ProvenanceResource(resource=URI(textrepo_version_url), relation='primary')]
    )
    provenance_id = pc.add_provenance(prov_data)
    logger.info(f"provenance location: {provenance_id.location} / {str(provenance_id.location).replace('/prov/', '#')}")


def upload(year: int, data_dir: str, trc: TextRepoClient, idx, prov_url: str, prov_key: str):
    # harvest_date = data_dir.split("/")[-1]
    export_for_text_repo(data_dir, idx, "phys",
                         f"{data_dir}/{year}/" + "textstore" + f"-{year}.json",
                         prov_key, prov_url,
                         trc,
                         'segmented_text',
                         year)
    export_for_text_repo(data_dir, idx, "log",
                         f"{data_dir}/{year}/" + "logical-textstore" + f"-{year}.json",
                         prov_key, prov_url,
                         trc,
                         'logical_segmented_text',
                         year)


def export_for_text_repo(data_dir, idx, phys_log, path, prov_key, prov_url, trc, type_name, year):
    if exists(path):
        logger.info(f"<= {path}")
        with open(path) as f:
            contents = f.read()
        external_id = f"volume-{year}"
        version_id = trc.import_version(external_id=external_id,
                                        type_name=type_name,
                                        contents=contents,
                                        allow_new_document=True,
                                        as_latest_version=True)
        if year not in idx:
            idx[year] = {}
        idx[year][phys_log] = version_id.version_id
        write_json(idx)
        logger.info(f"verify: {trc.base_uri}/view/versions/{version_id.version_id}/segments/index/0/39")
        store_provenance(textrepo_version_url=f"{trc.base_uri}/rest/versions/{version_id.version_id}",
                         session_files_path=f"{data_dir}/{year}/sessions",
                         year=year,
                         provenance_url=prov_url,
                         provenance_api_key=prov_key)
    else:
        logger.error(f"file not found: {path}")


def load_version_id_idx(version_id_idx_path: str):
    if exists(version_id_idx_path):
        # logger.info(f"<= {version_id_idx_path}")
        # with open(version_id_idx_path) as f:
        #     return json.load(f)
        return read_json(version_id_idx_path)
    else:
        return {}


@logger.catch
def main():
    parser = argparse.ArgumentParser(
        description="Upload the text-stores of the given year(s), and save its version id",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("year",
                        help="The year(s) to upload to textrepo",
                        nargs='+',
                        type=int)
    parser.add_argument("-d", "--data-dir",
                        help="The directory where to find the textstore json",
                        required=True,
                        type=str)
    parser.add_argument("-t",
                        "--textrepo-base-url",
                        required=True,
                        help="The base URL of the TextRepo server containing the text the annotations refer to "
                             "( example: "
                             "https://textrepo.republic-caf.diginfra.org/api/ )",
                        type=str,
                        metavar="textrepo_base_url")
    parser.add_argument("-p",
                        "--provenance-base-url",
                        required=True,
                        help="The base URL of the provenance server to send provenance to.",
                        type=str,
                        metavar="provenance_base_url")
    parser.add_argument("-k",
                        "--provenance-api-key",
                        required=True,
                        help="The api-key of the provenance server to send provenance to.",
                        type=str,
                        metavar="provenance_ap_key")

    args = parser.parse_args()
    years = args.year
    data_dir = trim_trailing_slash(args.data_dir)
    version_id_idx = load_version_id_idx(version_id_idx_path)
    trc = TextRepoClient(args.textrepo_base_url, verbose=True)
    add_segmented_text_type_if_missing(trc)
    prov_url = args.provenance_base_url
    prov_key = args.provenance_api_key
    for year in sorted(years):
        upload(year, data_dir, trc, version_id_idx, prov_url, prov_key)
    logger.info("done!")


if __name__ == '__main__':
    main()
