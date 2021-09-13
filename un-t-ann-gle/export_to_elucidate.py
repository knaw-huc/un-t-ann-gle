#!/bin/env python

import json
import os

import sys
sys.path.append('../../elucidate-python-client/elucidate')

from client import split_annotation, ElucidateClient
from icecream import ic

from utils import default_progress_bar


def main():
    annotations_json = 'web_annotations.json'
    print(f"- reading {annotations_json}...", end='')
    with open(annotations_json) as f:
        web_annotations = json.load(f)
    print()
    export_to_elucidate(web_annotations)


def export_to_elucidate(web_annotations):
    ec = ElucidateClient("https://elucidate.tt.di.huc.knaw.nl/annotation")
    container_name = "republic_1728_06_19"
    container_url = "https://elucidate.tt.di.huc.knaw.nl/annotation/w3c/republic-1728-06-19/"
#    container_id = ec.read_container_identifier(container_name)
#    if not container_id:
#        container_id = ec.create_container(label=container_name, container_id=container_name)
#    ic(container_id)

    uploaded_json = "last_uploaded.json"
    if os.path.exists(uploaded_json):
        with open(uploaded_json) as f:
            last_uploaded = json.load(f)
        print(f"- resuming upload, starting at annotation {last_uploaded + 1} / {len(web_annotations)}:")
    else:
        print(f"- uploading {len(web_annotations)} annotations:")
        last_uploaded = -1
#    bar = default_progress_bar(len(web_annotations) - last_uploaded)
    for i, wa in enumerate(web_annotations):
        if i > last_uploaded:
#            bar.update(i - last_uploaded)
            (body, target, custom) = split_annotation(wa)
            ec.create_annotation(container_url=container_url, body=body, target=target, custom=custom)
            with open(uploaded_json, 'w') as f:
                json.dump(i, f)
    print()


if __name__ == '__main__':
    main()
