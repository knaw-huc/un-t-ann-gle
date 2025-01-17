#!/usr/bin/env python3
import sys

from loguru import logger

import untanngle.textfabric as tf

project_name = 'translatin'


@logger.catch()
def main(version: str):
    config = tf.TFUntangleConfig(
        project_name=project_name,
        data_path=f'data/{project_name}/{version}/prod',
        export_path=f'out',
        textrepo_base_uri=f'https://{project_name}.tt.di.huc.knaw.nl/textrepo',
        excluded_types=[],
        tier0_type='tei:Work',
        with_facsimiles=False
    )
    tf.untangle_tf_export(config)


if __name__ == '__main__':
    main(sys.argv[1])
