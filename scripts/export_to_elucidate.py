#!/bin/env python

import json
import os

import elucidate.tools as et
from elucidate.client import ElucidateClient

# elucidate_base_url = "https://elucidate.tt.di.huc.knaw.nl/annotation"
elucidate_base_url = "http://localhost:18080/annotation"


def main():
    annotations_json = 'web_annotations.json'
    print(f"- reading {annotations_json}...", end='')
    with open(annotations_json) as f:
        web_annotations = json.load(f)
    print()
    export_to_elucidate(web_annotations)


def export_to_elucidate(web_annotations):
    ec = ElucidateClient(elucidate_base_url)
    container_name = "republic_1728_06_19"
    container_id = ec.read_container_identifier(container_name)
    if not container_id:
        container_id = ec.create_container(label=container_name, container_id=container_name)
    #    ic(container_id)
    # container_url = "https://elucidate.tt.di.huc.knaw.nl/annotation/w3c/republic-1728-06-19/"

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
            (body, target, custom) = et.split_annotation(wa)
            ec.create_annotation(container_id=container_id, body=body, target=target, custom=custom)
            with open(uploaded_json, 'w') as f:
                json.dump(i, f)
    print()


if __name__ == '__main__':
    main()
