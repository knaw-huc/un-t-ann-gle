import itertools
import json
from collections import defaultdict
from itertools import zip_longest
from typing import Any, Callable, Tuple, Union
from typing import List, Dict

import progressbar
from loguru import logger
from textrepo.client import TextRepoClient

import untanngle.textfabric as tf


def default_progress_bar(max_value):
    widgets = [' [',
               progressbar.Timer(format='elapsed time: %(elapsed)s'),
               '] ',
               progressbar.Bar('*'),
               ' (',
               progressbar.ETA(),
               ') ',
               ]
    return progressbar.ProgressBar(max_value=max_value,
                                   widgets=widgets).start()


def trc_has_document_with_external_id(trc: TextRepoClient, external_id: str) -> bool:
    try:
        metadata = trc.find_document_metadata(external_id)
        return metadata is not None
    except Exception:
        return False


def add_segmented_text_type_if_missing(client: TextRepoClient):
    name = "segmented_text"
    available_type_names = [t.name for t in client.read_file_types()]
    if name not in available_type_names:
        client.create_file_type(name=name, mimetype="application/json")


def add_logical_segmented_text_type_if_missing(client: TextRepoClient):
    name = "logical_segmented_text"
    available_type_names = [t.name for t in client.read_file_types()]
    if name not in available_type_names:
        client.create_file_type(name=name, mimetype="application/json")


def upload_to_tr(textrepo_base_uri: str, project_name: str, tf_text_files: list[str]) -> dict[str, dict[str, str]]:
    trc = TextRepoClient(textrepo_base_uri)
    add_segmented_text_type_if_missing(trc)
    add_logical_segmented_text_type_if_missing(trc)
    versions = defaultdict(lambda: {})
    for tf_text_file in tf_text_files:
        file_num = tf._get_file_num(tf_text_file)
        external_id = f"{project_name}-{file_num}"
        logger.info(f"<= {tf_text_file}")
        with open(tf_text_file) as f:
            content = f.read()
        if not trc_has_document_with_external_id(trc, external_id):
            document_identifier = trc.create_document(external_id)
            trc.set_document_metadata(document_identifier.id, "project", project_name)
        if "logical" in tf_text_file:
            type = "logical"
            tr_type = "logical_segmented_text"
        else:
            type = "physical"
            tr_type = "segmented_text"
        version_id = trc.import_version(external_id=external_id,
                                        type_name=tr_type,
                                        contents=content,
                                        as_latest_version=True)
        versions[file_num][type] = version_id.version_id
    return versions


def store_web_annotations(web_annotations, export_path: str):
    logger.info(f"=> {export_path}")
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(obj=web_annotations, fp=f, indent=2, ensure_ascii=False)


def show_annotation_counts(web_annotations: List[Dict[str, Any]], excluded_types):
    print()
    print("Annotation types:")
    typed_annotations = [a for a in web_annotations if "type" in a["body"]]
    typed_annotations.sort(key=lambda a: a['body']['type'])
    grouped = itertools.groupby(typed_annotations, lambda a: a['body']['type'])
    counts = []
    for atype, anno_group in grouped:
        counts.append([atype, len([a for a in anno_group])])
    counts.sort(key=lambda t: t[1])
    max_type_name_size = max([len(t[0]) for t in counts])
    for t in counts:
        body_type = t[0]
        if body_type in excluded_types:
            excluded = " (excluded)"
        else:
            excluded = ""
        print(f"{body_type :{max_type_name_size}}: {t[1]}{excluded}")
    print()


def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


def chunk_list(big_list: List[Any], chunk_size: int) -> List[List[Any]]:
    return [[i for i in item if i] for item in list(zip_longest(*[iter(big_list)] * chunk_size))]


def read_json(path: str) -> Any:
    logger.info(f"<= {path}")
    with open(path, "r") as f:
        data = json.load(f)
    return data


# def write_json(output_path: str):
#     logger.info(f"=> {version_id_idx_path}")
#     with open(version_id_idx_path, "w") as f:
#         json.dump(output_path, fp=f, ensure_ascii=False)


def transform_dict_entries(
        data: Union[dict, list],
        entry_filter: Callable[[str, Any], bool],
        entry_transformer: Callable[[str, Any], Tuple[str, Any]]
) -> Any:
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            if entry_filter(key, value):
                new_key, new_value = entry_transformer(key, value)
            else:
                new_key, new_value = key, value
            new_dict[new_key] = transform_dict_entries(new_value, entry_filter, entry_transformer)
        return new_dict
    elif isinstance(data, list):
        return [transform_dict_entries(item, entry_filter, entry_transformer) for item in data]
    else:
        return data
