#!/usr/bin/env python3
import argparse

from loguru import logger

import untanngle.annorepo_tools as ar
from untanngle.utils import trim_trailing_slash


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Upload a list of web annotations to an annorepo server in the given container "
                    "(which will be created if it does not already exist)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("input",
                        help="The json file containing the list of annotations, or a directory containing these json files",
                        nargs="*",
                        type=str)
    parser.add_argument("-a",
                        "--annorepo-base-url",
                        required=True,
                        help="The base URL of the AnnoRepo server to upload the annotations to.",
                        type=str,
                        metavar="annorepo_base_url")
    parser.add_argument("-c",
                        "--container-id",
                        required=True,
                        help="The id of the container the annotations should be added to. "
                             "(will be created if it does not already exist)",
                        type=str,
                        metavar="container_id")
    parser.add_argument("-l",
                        "--container-label",
                        help="The label to give the container, if it needs to be created.",
                        type=str,
                        metavar="container_label")
    parser.add_argument("-k",
                        "--api-key",
                        help="The api-key to get access to the annorepo api",
                        type=str,
                        metavar="api_key")
    args = parser.parse_args()
    annorepo_base_url = trim_trailing_slash(args.annorepo_base_url)
    if args.container_label:
        ar.upload(
            annorepo_base_url, args.container_id, args.input, args.container_label, api_key=args.api_key,
            show_progress=True
        )
    else:
        ar.upload(
            annorepo_base_url, args.container_id, args.input, api_key=args.api_key, show_progress=True
        )


if __name__ == '__main__':
    main()
