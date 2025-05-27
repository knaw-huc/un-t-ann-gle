#!/usr/bin/env python3
import sys

from loguru import logger

import untanngle.textfabric as tf

project_name = "vangogh"


@logger.catch()
def main(version: str):
    config = tf.TFUntangleConfig(
        project_name=project_name,
        data_path=f'data/{project_name}/{version}',
        export_path=f'out',
        textsurf_base_uri_internal=None,
        textsurf_base_uri_external=f"https://textsurf.di.huc.knaw.nl/{project_name}",
        excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk", "nlp:Sentence"],
        tier0_type='tf:Letter',
        show_progress=True,
        editem_project=True
    )
    tf.untangle_tf_export(config)


if __name__ == '__main__':
    main(sys.argv[1])
