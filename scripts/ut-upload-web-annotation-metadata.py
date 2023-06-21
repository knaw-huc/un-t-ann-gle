#!/usr/bin/env python3
import argparse
import json
from time import sleep

import requests
from icecream import ic
from loguru import logger

url = "https://switch.sd.di.huc.knaw.nl/textanno"


def process(path: str):
    with open(path) as f:
        annotations = json.load(f)

    response = requests.post(
        url=url,
        json=annotations
    )

    ic(response.request.headers)
    ic(response.headers)
    if not response.status_code == 202:
        logger.error(f"response={response}")
        raise Exception(f"server returned error: {response.text}")
    status_url = response.headers['Location']
    ready = False
    while not ready:
        status_response = requests.get(status_url)
        match status_response.status_code:
            case 302:
                ready = True
            case 200:
                ready = False
                sleep(1)
            case _:
                ic(status_response)
                raise Exception("unexpected response")

    result_location = status_response.headers['Location']
    result_response = requests.get(result_location)
    metadata_map = result_response.json()
    for a in annotations:
        a_id = a["id"]
        if "metadata" in a:
            a["metadata"]["tt:url"] = metadata_map[a_id]
    with open(f"{path}.new", "w") as f:
        json.dump(annotations, f)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Upload a web annotations file to the sd textanno server and add the returned urls to the annotation metadata.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("inputfile",
                        help="The json file with the web-annotations",
                        type=str)
    args = parser.parse_args()
    return args


@logger.catch
def main():
    args = parse_args()
    process(args.inputfile)


if __name__ == '__main__':
    main()
