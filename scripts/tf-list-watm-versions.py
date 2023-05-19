#!/usr/bin/env python3

import requests
from loguru import logger


@logger.catch()
def main():
    base_url = 'https://api.github.com/repos'
    owner = 'annotation'
    repo = 'mondriaan'
    path = 'watm'
    url = f'{base_url}/{owner}/{repo}/contents/{path}'
    response = requests.get(url)
    if response.status_code == 200:
        contents = response.json()
        for item in contents:
            print(item['name'])
    else:
        print(f"Failed to list directory: {response.status_code}")


if __name__ == '__main__':
    main()
