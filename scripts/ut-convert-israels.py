#!/usr/bin/env python3
import sys

from loguru import logger

import untanngle.textfabric as tf

project_name = "israels"

iiif_base_url = f"https://preview.dev.diginfra.org/iiif/3/{project_name}|HuygensING|{project_name}|scans|"


def graphic_url_to_iiif_base_url(url: str) -> str:
    if url.startswith("ii"):
        return f"{iiif_base_url}illustrations|{url}.jpg"
    else:
        return f"{iiif_base_url}pages|{url}.jpg"


@logger.catch()
def main(version: str):
    config = tf.TFUntangleConfig(
        project_name=project_name,
        data_path=f'data/{project_name}/{version}',
        export_path=f'out',
        textrepo_base_uri_internal=None,
        textrepo_base_uri_external=f"https://{project_name}.tt.di.huc.knaw.nl/textrepo",
        excluded_types=["tei:Lb", "tei:Pb", "nlp:Token", "tf:Chunk", "nlp:Sentence"],
        tier0_type='tf:Letter',
        show_progress=True,
        editem_project=True,
        apparatus_data_directory=f"/Users/bram/workspaces/editem/editem-apparatus/out/{project_name}",
        graphic_url_mapper=graphic_url_to_iiif_base_url
    )
    errors = tf.untangle_tf_export(config)
    if errors:
        print("errors:")
        for error in errors:
            print(f"- {error}")


if __name__ == '__main__':
    main(sys.argv[1])
