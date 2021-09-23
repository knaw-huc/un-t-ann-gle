#!/usr/bin/env python3
import argparse
import json
import os

import elucidate.tools as et
from elucidate.client import ElucidateClient


def main():
    parser = argparse.ArgumentParser(
        description="upload the annotations from web_annotations.json to a given AnnotationContainer on an elucidate server.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-e",
                        "--elucidate-base-url",
                        help="The base URL for the elucidate server",
                        type=str,
                        default='https://elucidate.tt.di.huc.knaw.nl/annotation',
                        metavar="elucidate_base_url")
    parser.add_argument("-c",
                        "--container-name",
                        help="The id of the AnnotationContainer to add the annotations to (will be created if it doesn't exist)",
                        type=str,
                        default='annotation_container',
                        metavar="container_name")
    args = parser.parse_args()
    read_and_export(args.elucidate_base_url, args.container_name)


def read_and_export(elucidate_base_url: str, container_name: str):
    annotations_json = 'web_annotations.json'
    print(f"- reading {annotations_json}...", end='')
    with open(annotations_json) as f:
        web_annotations = json.load(f)
    print()
    export_to_elucidate(web_annotations, elucidate_base_url, container_name)


def export_to_elucidate(web_annotations, elucidate_base_url, container_name):
    ec = ElucidateClient(elucidate_base_url)
    container_id = ec.read_container_identifier(container_name)
    if not container_id:
        container_id = ec.create_container(label=container_name, container_id=container_name)
    #    ic(container_id)
    # container_url = "https://elucidate.tt.di.huc.knaw.nl/annotation/w3c/republic-1728-06-19/"

    uploaded_json = "last_uploaded.json"
    if os.path.exists(uploaded_json):
        with open(uploaded_json) as f:
            last_uploaded = json.load(f)
        print(
            f"- resuming upload to {container_id.url}, starting at annotation {last_uploaded + 1} / {len(web_annotations)}:")
    else:
        print(f"- uploading {len(web_annotations)} annotations to {container_id.url}:")
        last_uploaded = -1
    #    bar = default_progress_bar(len(web_annotations) - last_uploaded)
    for i, wa in enumerate(web_annotations):
        if i > last_uploaded:
            #            bar.update(i - last_uploaded)
            (body, target, custom, custom_contexts) = et.split_annotation(wa)
            ec.create_annotation(container_id=container_id, body=body, target=target, custom=custom,
                                 custom_contexts=custom_contexts)
            with open(uploaded_json, 'w') as f:
                json.dump(i, f)
    print()
    if os.path.exists(uploaded_json):
        os.remove(uploaded_json)


if __name__ == '__main__':
    main()
# elucidate_base_url = "https://elucidate.tt.di.huc.knaw.nl/annotation"
# elucidate_base_url = "http://localhost:18080/annotation"
