#!/usr/bin/env python3
import glob

from loguru import logger

import untanngle.textfabric as tf

basedir = 'data/suriano/0.0.5'
text_files = sorted(glob.glob(f'{basedir}/text-*.json'))
anno_files = sorted(glob.glob(f"{basedir}/anno-*.json"))
textrepo_base_uri = "https://suriano.tt.di.huc.knaw.nl/textrepo"
project_name = "suriano"
export_path = f"out/{project_name}-web_annotations.json"
excluded_types = ["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk"]
tier0_type = "tf:File"


@logger.catch()
def main():
    tf.untangle_tf_export(project_name=project_name, text_files=text_files, anno_files=anno_files,
                          textrepo_base_uri=textrepo_base_uri, export_path=export_path, tier0_type=tier0_type,
                          excluded_types=excluded_types)


if __name__ == '__main__':
    main()