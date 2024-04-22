#!/usr/bin/env python3
import glob

from loguru import logger

import untanngle.textfabric as tf

project_name = "vangogh"
basedir = 'data/vangogh/0.2.0'

config = tf.TFUntangleConfig(
    project_name=project_name,
    text_files=sorted(glob.glob(f'{basedir}/text-*.tsv')),
    anno_files=sorted(glob.glob(f"{basedir}/anno-*.tsv")),
    anno2node_path=f"{basedir}/anno2node.tsv",
    textrepo_base_uri=None,
    # textrepo_base_uri = f"https://{project_name}.tt.di.huc.knaw.nl/textrepo",
    export_path=f"out/{project_name}-web_annotations.json",
    excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk", "nlp:Sentence"],
    tier0_type="tf:File"
)


@logger.catch()
def main():
    tf.untangle_tf_export(config)


if __name__ == '__main__':
    main()
