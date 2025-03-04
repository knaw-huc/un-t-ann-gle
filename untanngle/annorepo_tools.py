import glob
import json
import os
from collections import Counter

import progressbar
import requests
from annorepo.client import AnnoRepoClient, ContainerAdapter

import untanngle.utils as uu


def get_etag(ca: ContainerAdapter) -> str:
    ar_base_url = ca.client.base_url
    response = requests.head(url=f'{ar_base_url}/w3c/{ca.container_name}')
    return response.headers['etag']


def upload(
        annorepo_base_url: str,
        container_id: str,
        input_paths: list[str],
        container_label: str = 'A Container for Web Annotations',
        api_key: str = None,
        overwrite_container: bool = False,
        show_progress: bool = False
):
    ar = AnnoRepoClient(annorepo_base_url, verbose=False, api_key=api_key)

    # ar_about = ar.get_about()
    # print(f"AnnoRepo server at {annorepo_base_url}:\n"
    #       f"- version {ar_about['version']}\n"
    #       f"- running since {ar_about['startedAt']}")

    ca = ar.container_adapter(container_name=container_id)
    container_url = f"{annorepo_base_url}/w3c/{container_id}"
    if ca.exists() and overwrite_container:
        etag = get_etag(ca)
        ca.delete(etag=etag, force=True)
    if not ca.exists():
        print(f"container {container_url} not found, creating...")
        ca.create(label=container_label)
    ca.set_anonymous_user_read_access(has_read_access=True)

    input_files = []
    for p in input_paths:
        if os.path.isdir(p):
            input_files.extend(glob.glob(f'{p}/*.json'))
        else:
            input_files.append(p)
    body_type_counter = Counter()
    if show_progress:
        widgets = [
            '[',
            progressbar.SimpleProgress(),
            progressbar.Bar(marker='\x1b[32m#\x1b[39m'),
            progressbar.Timer(),
            '|',
            progressbar.ETA(),
            ']'
        ]
        with progressbar.ProgressBar(widgets=widgets, max_value=len(input_files), redirect_stdout=True) as bar:
            for i, input_file in enumerate(input_files):
                process_web_annotations_file(annorepo_base_url, ar, body_type_counter, container_id, input_file, True)
                bar.update(i)
    else:
        for input_file in input_files:
            process_web_annotations_file(annorepo_base_url, ar, body_type_counter, container_id, input_file, False)

    print_report(body_type_counter, container_url)
    add_indexes(ca)
    preload_distinct_body_type_cache(ca)
    print("done!")


def add_indexes(ca):
    ca.create_compound_index(
        {
            "target.type": "ascending",
            "target.source": "ascending",
            "target.selector.type": "ascending",
            "target.selector.start": "ascending",
            "target.selector.end": "ascending"
        }
    )
    ca.create_compound_index({"body.id": "hashed"})
    ca.create_compound_index({"body.type": "hashed"})


def process_web_annotations_file(
        annorepo_base_url: str,
        ar: AnnoRepoClient,
        body_type_counter: Counter,
        container_id: str,
        input_file: str,
        show_progress: bool
):
    print(f"reading {input_file}...")
    with open(input_file) as f:
        annotation_list = json.load(f)
    for a in [a for a in annotation_list if 'body' in a and 'type' in a['body']]:
        body_type = a['body']['type']
        # ic(body_type)
        if isinstance(body_type, list):
            body_type = body_type[0]
        body_type_counter.update([body_type])
    number_of_annotations = len(annotation_list)
    print(f"  {number_of_annotations} annotations found.")
    chunk_size = 500
    chunked_annotations = uu.chunk_list(annotation_list, chunk_size)
    number_of_chunks = len(chunked_annotations)
    print(
        f"  uploading {number_of_annotations} annotations to {annorepo_base_url}/w3c/{container_id}"
        f" in {number_of_chunks} chunks of at most {chunk_size} annotations ...")
    annotation_ids = []
    for p, chunk in enumerate(chunked_annotations):
        if show_progress:
            print(f"    chunk ({p + 1}/{number_of_chunks})", end='\r')
        # ic(chunk)
        annotation_ids.extend(ar.add_annotations(container_id, chunk))
    print()
    out_path = "/".join(input_file.split("/")[:-1])
    input_file_name_base = input_file.split("/")[-1].replace(".json", "")
    outfile = f"{out_path}/{input_file_name_base}-annotation_ids.json"
    annotation_id_mapping = {a["id"]: f"{annorepo_base_url}/w3c/{b['containerName']}/{b['annotationName']}"
                             for a, b in zip(annotation_list, annotation_ids)}
    print(f"=> {outfile}")
    with open(outfile, "w") as f:
        json.dump(annotation_id_mapping, fp=f)


def preload_distinct_body_type_cache(ca):
    distinct_body_types = ca.read_distinct_values('body.type')


def print_report(body_type_counter, container_url):
    counts = [c for c in body_type_counter.items()]
    sorted_counts = sorted(counts, key=lambda x: x[1])
    print(f"container: {container_url}")
    print(f"typed annotations: {body_type_counter.total()}")
    print()
    print("Annotation types:")
    max_type_name_size = max([len(t[0]) for t in counts])
    for t in sorted_counts:
        body_type = t[0]
        print(f"{body_type :{max_type_name_size}}: {t[1]}")
    print()
