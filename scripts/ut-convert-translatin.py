#!/usr/bin/env python3
import json
from glob import glob

from loguru import logger
from textrepo.client import TextRepoClient

from untanngle import textfabric


def upload_segmented_text(external_id: str, text_file_path: str, client: TextRepoClient) -> str:
    with open(text_file_path) as f:
        content = f.read()
    version_id = client.import_version(external_id=external_id,
                                       type_name='segmented_text',
                                       contents=content,
                                       as_latest_version=True)
    return version_id.version_id


def check_file_types(client: TextRepoClient):
    name = "segmented_text"
    available_type_names = [t.name for t in client.read_file_types()]
    if name not in available_type_names:
        client.create_file_type(name=name, mimetype="application/json")


@logger.catch()
def main():
    basedir = 'data/translatin'
    textrepo_url = "https://translatin.tt.di.huc.knaw.nl/textrepo"
    trc = TextRepoClient(base_uri=textrepo_url)
    check_file_types(trc)

    for dir in glob(f"{basedir}/*/"):
        base = dir.split('/')[-2]
        anno_file_path = f'{dir}anno.json'
        text_file_path = f'{dir}text.json'
        logger.info(f"<= {text_file_path}")
        tr_version_id = upload_segmented_text(base, text_file_path, trc)
        logger.info(f"<= {anno_file_path}")
        web_annotations = textfabric.convert(project=f'translatin:{base}',
                                             anno_file=anno_file_path,
                                             text_file=text_file_path,
                                             textrepo_url=textrepo_url,
                                             textrepo_file_version=tr_version_id)
        export_path = f"out/translatin-{base}-web_annotations.json"
        logger.info(f"=> {export_path}")
        with open(export_path, 'w') as f:
            json.dump(web_annotations, fp=f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    main()
