#!/usr/bin/env python3
import argparse
import json
from itertools import zip_longest
from typing import List, Any

from annorepo.client import AnnoRepoClient


def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
    return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]


def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


def upload(annorepo_base_url: str, container_id: str, inputfile: str,
           container_label: str = 'A Container for Web Annotations'):
    ar = AnnoRepoClient(annorepo_base_url, verbose=False)
    ar_about = ar.get_about()
    print(f"AnnoRepo server at {annorepo_base_url}:\n"
          f"- version {ar_about['version']}\n"
          f"- running since {ar_about['startedAt']}")

    if not ar.has_container(container_id):
        print(f"container {annorepo_base_url}/w3c/{container_id} not found, creating...")
        ar.create_container(name=container_id, label=container_label)

    print(f"reading {inputfile}...")
    with open(inputfile) as f:
        annotation_list = json.load(f)
    number_of_annotations = len(annotation_list)

    print(f"{number_of_annotations} annotations found.")

    chunk_size = 150
    chunked_annotations = chunk_list(annotation_list, chunk_size)
    number_of_chunks = len(chunked_annotations)
    print(
        f"uploading {number_of_annotations} annotations to {annorepo_base_url}/w3c/{container_id}"
        f" in {number_of_chunks} chunks of at most {chunk_size} annotations ...")
    for i, chunk in enumerate(chunked_annotations):
        print(f"chunk ({i+1}/{number_of_chunks})", end='\r')
        annotation_ids = ar.add_annotations(container_id, chunk)
    print()
    print("done!")


def main():
    parser = argparse.ArgumentParser(
        description="Upload a list of web annotations to an annorepo server in the given container "
                    "(which will be created if it does not already exist)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("inputfile",
                        help="The json file containing the list of annotations",
                        type=str)
    parser.add_argument("-a",
                        "--annorepo-base-url",
                        required=True,
                        help="The base URL of the AnnoRepo server to upload the annotations to.",
                        type=str,
                        metavar="annorepo_base_url")
    parser.add_argument("-c",
                        "--container-id",
                        required=True,
                        help="The id of the container the annotations should be added to. "
                             "(will be created if it does not already exist)",
                        type=str,
                        metavar="container_id")
    parser.add_argument("-l",
                        "--container-label",
                        help="The label to give the container, if it needs to be created.",
                        type=str,
                        metavar="container_label")
    args = parser.parse_args()
    annorepo_base_url = trim_trailing_slash(args.annorepo_base_url)
    if args.container_label:
        upload(annorepo_base_url, args.container_id, args.inputfile, args.container_label)
    else:
        upload(annorepo_base_url, args.container_id, args.inputfile)


if __name__ == '__main__':
    main()