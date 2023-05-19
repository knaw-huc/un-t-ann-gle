#!/usr/bin/env python3
import json

import mondriaan
from loguru import logger


@logger.catch()
def main():
    basedir = 'data'

    textfile = f'{basedir}/mondriaan-text.json'
    anno_file = f"{basedir}/mondriaan-anno.json"
    web_annotations = mondriaan.convert(anno_file=anno_file,
                                        text_file=textfile,
                                        textrepo_url="https://mondriaan.tt.di.huc.knaw.nl/textrepo",
                                        textrepo_file_version="c637abd5-7e07-4a3d-962e-fb40d4656ec4")
    # selection = [w for w in web_annotations if w["body"]["type"] in ("tei:Pb", "tei:Div")]
    # print(json.dumps(selection, indent=2))
    print(json.dumps(web_annotations, indent=2))


if __name__ == '__main__':
    main()
