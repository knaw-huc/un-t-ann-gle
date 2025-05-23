#!/usr/bin/env python3
import sys

from loguru import logger

import untanngle.textfabric as tf

project_name = 'mondriaan'


@logger.catch()
def main(version: str):
    config = tf.TFUntangleConfig(
        project_name=project_name,
        data_path=f'data/{project_name}/{version}',
        export_path=f'out',
        textrepo_base_uri_internal=f'https://{project_name}.tt.di.huc.knaw.nl/textrepo',
        textrepo_base_uri_external=f'https://{project_name}.tt.di.huc.knaw.nl/textrepo',
        excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk"],
        tier0_type='tf:File',
        show_progress=True
    )
    tf.untangle_tf_export(config)


if __name__ == '__main__':
    main(sys.argv[1])
