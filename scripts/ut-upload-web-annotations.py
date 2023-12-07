#!/usr/bin/env python3
import argparse
import glob
import json
import os.path
from itertools import zip_longest
from typing import List, Any

import progressbar
from annorepo.client import AnnoRepoClient
from loguru import logger


def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
    return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]


def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


tier_metadata_fields = ['volume', 'na:File']


def upload(annorepo_base_url: str,
           container_id: str,
           input: List[str],
           container_label: str = 'A Container for Web Annotations',
           api_key: str = None):
    ar = AnnoRepoClient(annorepo_base_url, verbose=False, api_key=api_key)
    # ar_about = ar.get_about()
    # print(f"AnnoRepo server at {annorepo_base_url}:\n"
    #       f"- version {ar_about['version']}\n"
    #       f"- running since {ar_about['startedAt']}")

    ca = ar.container_adapter(container_name=container_id)
    if not ca.exists():
        print(f"container {annorepo_base_url}/w3c/{container_id} not found, creating...")
        ca.create(label=container_label)
        ca.create_index(field='body.id', index_type='hashed')
        ca.create_index(field='body.type', index_type='hashed')
        # for overlap queries
        ca.create_index(field='target.source', index_type='ascending')
        ca.create_index(field='target.selector.type', index_type='ascending')
        ca.create_index(field='target.selector.start', index_type='ascending')
        ca.create_index(field='target.selector.end', index_type='ascending')
        for f in tier_metadata_fields:
            ar.create_index(field=f'body.metadata.{f}', index_type='hashed')
    ca.set_anonymous_user_read_access(has_read_access=True)

    inputfiles = []
    for p in input:
        if os.path.isdir(p):
            inputfiles.extend(glob.glob(f'{p}/*.json'))
        else:
            inputfiles.append(p)
    widgets = [
        '[',
        progressbar.SimpleProgress(),
        progressbar.Bar(marker='\x1b[32m#\x1b[39m'),
        progressbar.Timer(),
        '|',
        progressbar.ETA(),
        ']'
    ]
    with progressbar.ProgressBar(widgets=widgets, max_value=len(inputfiles), redirect_stdout=True) as bar:
        for i, inputfile in enumerate(inputfiles):
            print(f"reading {inputfile}...")
            with open(inputfile) as f:
                annotation_list = json.load(f)
            number_of_annotations = len(annotation_list)

            print(f"  {number_of_annotations} annotations found.")

            chunk_size = 30000
            chunked_annotations = chunk_list(annotation_list, chunk_size)
            number_of_chunks = len(chunked_annotations)
            print(
                f"  uploading {number_of_annotations} annotations to {annorepo_base_url}/w3c/{container_id}"
                f" in {number_of_chunks} chunks of at most {chunk_size} annotations ...")
            annotation_ids = []
            for p, chunk in enumerate(chunked_annotations):
                print(f"    chunk ({p + 1}/{number_of_chunks})", end='\r')
                annotation_ids.extend(ar.add_annotations(container_id, chunk))
            print()
            # out_path = "/".join(inputfile.split("/")[:-1])
            # outfile = f"{out_path}/annotation_ids.json"
            # print(f"=> {outfile}")
            # annotation_id_mapping = {a["id"]: f"{annorepo_base_url}/w3c/{b['containerName']}/{b['annotationName']}"
            #                          for a, b in zip(annotation_list, annotation_ids)}
            # with open(outfile, "w") as f:
            #     json.dump(annotation_id_mapping, fp=f)
            bar.update(i)
    print("done!")


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Upload a list of web annotations to an annorepo server in the given container "
                    "(which will be created if it does not already exist)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("input",
                        help="The json file containing the list of annotations, or a directory containing these json files",
                        nargs="*",
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
    parser.add_argument("-k",
                        "--api-key",
                        help="The api-key to get access to the annorepo api",
                        type=str,
                        metavar="api_key")
    args = parser.parse_args()
    annorepo_base_url = trim_trailing_slash(args.annorepo_base_url)
    if args.container_label:
        upload(annorepo_base_url, args.container_id, args.input, args.container_label, api_key=args.api_key)
    else:
        upload(annorepo_base_url, args.container_id, args.input, api_key=args.api_key)


if __name__ == '__main__':
    main()
