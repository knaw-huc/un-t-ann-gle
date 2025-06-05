#!/usr/bin/env python3
from loguru import logger

from untanngle.intro_text_factory import IntroTextFactory, IntroTextConfig


@logger.catch()
def main():
    config = IntroTextConfig(
        intro_text_files=[
            "Inleiding_introduction",
            "Verantwoording_Notes_for_the_reader",
            "colofon",
            "woord-van-dank"
        ],
        input_xml_directory="/Users/bram/workspaces/editem/editem/data/working/prod/project/00000000000000000000000b/HuygensING/israels/tei/about/",
        output_xml_directory="/Users/bram/workspaces/editem/editem/data/working/prod/project/00000000000000000000000b/HuygensING/israels/tei/intro/"
    )
    itf = IntroTextFactory(config)
    errors = itf.merge_intro_text_files()
    if errors:
        print("errors:")
        for error in errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
