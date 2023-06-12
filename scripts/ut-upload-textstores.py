#!/usr/bin/env python3

import argparse
import json
from os.path import exists

from loguru import logger
from textrepo.client import TextRepoClient

version_id_idx_path = "out/version_id_idx.json"


def upload(year: int, data_dir: str, trc: TextRepoClient, idx):
    # harvest_date = data_dir.split("/")[-1]
    harvest_date = "230605"
    path = f"{data_dir}/{year}-textstore-{harvest_date}.json"
    if exists(path):
        logger.info(f"<= {path}")
        with open(path) as f:
            contents = f.read()
        external_id = f"volume-{year}"
        version_id = trc.import_version(external_id=external_id,
                                        type_name='segmented_text',
                                        contents=contents,
                                        allow_new_document=True,
                                        as_latest_version=True)
        idx[year] = version_id.version_id
        store_version_id_idx(idx)
    else:
        logger.error(f"file not found: {path}")


def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


def load_version_id_idx():
    if exists(version_id_idx_path):
        logger.info(f"<= {version_id_idx_path}")
        with open(version_id_idx_path) as f:
            return json.load(f)
    else:
        return {}


def store_version_id_idx(idx):
    logger.info(f"=> {version_id_idx_path}")
    with open(version_id_idx_path, "w") as f:
        json.dump(idx, fp=f)


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

    args = parser.parse_args()
    years = args.year
    data_dir = trim_trailing_slash(args.data_dir)
    version_id_idx = load_version_id_idx()
    trc = TextRepoClient(args.textrepo_base_url, verbose=True)
    for year in sorted(years):
        upload(year, data_dir, trc, version_id_idx)
    logger.info("done!")


if __name__ == '__main__':
    main()
