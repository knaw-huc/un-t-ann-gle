#!/usr/bin/env python3
import json

from loguru import logger

import textfabric

basedir = 'data/watm'
textfile = f'{basedir}/mondriaan-text.json'
anno_files = [f"{basedir}/mondriaan-anno.json"]
textrepo_base_uri = "https://mondriaan.tt.di.huc.knaw.nl/textrepo"
external_id = "mondriaan"


@logger.catch()
def main():
    web_annotations = textfabric.convert(project=external_id,
                                         anno_files=anno_files,
                                         text_file=textfile,
                                         textrepo_url=textrepo_base_uri,
                                         textrepo_file_version="c637abd5-7e07-4a3d-962e-fb40d4656ec4")
    # selection = [w for w in web_annotations if w["body"]["type"] in ("tei:Pb", "tei:Div")]
    # print(json.dumps(selection, indent=2))
    print(json.dumps(web_annotations, indent=2))


if __name__ == '__main__':
    main()
