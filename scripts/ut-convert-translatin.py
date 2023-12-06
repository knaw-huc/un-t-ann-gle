#!/usr/bin/env python3
import json
from glob import glob

from loguru import logger

from untanngle import textfabric


def upload_segmented_text(base: str, text_file_path: str) -> str:
    return 'dummy-version-id'


@logger.catch()
def main():
    basedir = 'data/translatin'

    for dir in glob(f"{basedir}/*/"):
        base = dir.split('/')[-2]
        anno_file_path = f'{dir}anno.json'
        text_file_path = f'{dir}text.json'
        logger.info(f"<= {text_file_path}")
        tr_version_id = upload_segmented_text(base, text_file_path)
        logger.info(f"<= {anno_file_path}")
        web_annotations = textfabric.convert(project=f'translatin:{base}',
                                             anno_file=anno_file_path,
                                             text_file=text_file_path,
                                             textrepo_url="https://translatin.tt.di.huc.knaw.nl/textrepo",
                                             textrepo_file_version=tr_version_id,
                                             text_in_body=True)
        export_path = f"out/translatin-{base}-web_annotations.json"
        logger.info(f"=> {export_path}")
        with open(export_path, 'w') as f:
            json.dump(web_annotations, fp=f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    main()
