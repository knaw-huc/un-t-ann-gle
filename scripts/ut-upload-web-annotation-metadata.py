#!/usr/bin/env python3
import argparse
import json
import random
from time import sleep

import requests
from icecream import ic
from loguru import logger

from untanngle.utils import chunk_list

url = "https://switch.sd.di.huc.knaw.nl/textanno"
chunk_size = 1_000_000


def process(path: str):
    logger.debug(f"<= {path}")
    with open(path) as f:
        annotations = json.load(f)

    chunked_annotations = chunk_list(annotations, chunk_size)
    noc = len(chunked_annotations)
    logger.debug(f"uploading {len(annotations)} annotations in {noc} chunk(s):")
    for i, chunk in enumerate(chunked_annotations):
        logger.debug(f"chunk {i + 1}/{noc}")
        upload_and_save_ref(annotations, chunk, path)


def upload_and_save_ref(annotations, chunk, path):
    logger.debug(f"POST {url}")
    response = requests.post(url=url, json=chunk)
    # ic(response.request.headers)
    # ic(response.headers)
    if not response.status_code == 202:
        logger.error(f"response={response}")
        raise Exception(f"server returned error: {response.text}")
    status_url = response.headers["Location"]
    ready = False
    retry_count = 0
    while not ready:
        sleep_time = calc_next_delay(retry_count)
        logger.debug(f"GET {status_url}")
        status_response = requests.get(status_url, allow_redirects=False)
        # logger.debug(f'<{status_response.status_code}>')
        match status_response.status_code:
            case 302:
                ready = True
            case 200:
                ready = False
                sleep(sleep_time)
                retry_count += 1
            case _:
                ic(status_response)
                raise Exception(f"unexpected response: {response.headers}")
    result_location = status_response.headers["Location"]
    logger.debug(f"GET {result_location}")
    result_response = requests.get(result_location)
    if result_response.status_code == 200:
        metadata_map = result_response.json()
        for a in annotations:
            body_id = a["body"]["id"]
            if "metadata" in a["body"] and body_id in metadata_map:
                a["body"]["metadata"]["rp:metadataUrl"] = metadata_map[body_id]
        logger.debug(f"=> {path}")
        with open(f"{path}", "w") as f:
            json.dump(annotations, f)
    else:
        ic(chunk)
        ic(result_response, result_response.content)
        exit(result_response.status_code)


def calc_next_delay(retry_count):
    max_delay = 60.0
    base_delay = 1
    factor = 2
    return min(max_delay, random.uniform(base_delay * factor ^ retry_count, max_delay))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Upload a web annotations file to the sd textanno server and add the returned urls to the annotation metadata.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "inputfile", help="The json file with the web-annotations", type=str
    )
    args = parser.parse_args()
    return args


@logger.catch
def main():
    args = parse_args()
    process(args.inputfile)


if __name__ == "__main__":
    main()
