#!/usr/bin/env python3
import glob

from loguru import logger

import untanngle.textfabric as tf

# basedir = 'data/vangogh/0.0.1'
basedir = 'data/vangogh/0.2.0'
text_files = sorted(glob.glob(f'{basedir}/text-*.tsv'))
anno_files = sorted(glob.glob(f"{basedir}/anno-*.tsv"))
anno2node_path = f"{basedir}/anno2node.tsv"
textrepo_base_uri: str = None
# textrepo_base_uri: str = "https://vangogh.tt.di.huc.knaw.nl/textrepo"
project_name = "vangogh"
export_path = f"out/{project_name}-web_annotations.json"
excluded_types = ["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk", "nlp:Sentence"]
tier0_type = "tf:File"


@logger.catch()
def main():
    tf.untangle_tf_export(
        project_name=project_name,
        text_files=text_files,
        anno_files=anno_files,
        textrepo_base_uri=textrepo_base_uri,
        anno2node_path=anno2node_path,
        export_path=export_path,
        tier0_type=tier0_type,
        text_in_body=False,
        excluded_types=excluded_types
    )


if __name__ == '__main__':
    main()
