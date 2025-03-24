#!/usr/bin/env python3
import sys

from loguru import logger

import untanngle.textfabric as tf

project_name = 'suriano'


@logger.catch()
def main(version: str):
    config = tf.TFUntangleConfig(
        project_name=project_name,
        data_path=f'data/{project_name}/{version}/prod',
        export_path=f'out',
        textrepo_base_uri_internal=f'https://textrepo.suriano.huygens.knaw.nl/api',
        textrepo_base_uri_external=f'https://textrepo.suriano.huygens.knaw.nl/api',
        excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk", "tf:Entity"],
        tier0_type='tf:Folder',
        show_progress=True
    )
    tf.untangle_tf_export(config)


if __name__ == '__main__':
    main(sys.argv[1])
