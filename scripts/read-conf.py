#!/usr/bin/env python3

import yaml
from icecream import ic
from loguru import logger


@logger.catch()
def main(conf_path: str):
    with open(conf_path, "r") as f:
        config = yaml.safe_load(f)
    ic(config)


if __name__ == '__main__':
    main('conf/test.conf')
