#!/usr/bin/env python3

from loguru import logger

import untanngle.textfabric as tf

project_name = 'suriano'

config = tf.TFUntangleConfig(
    project_name=project_name,
    data_path=f'data/{project_name}/0.2.0',
    export_path=f'out',
    textrepo_base_uri=f'https://{project_name}.tt.di.huc.knaw.nl/textrepo',
    excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk"],
    tier0_type='tf:File'
)


@logger.catch()
def main():
    tf.untangle_tf_export(config)


if __name__ == '__main__':
    main()
