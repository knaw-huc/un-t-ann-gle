#!/usr/bin/env python3
import argparse

import requests
from loguru import logger

type_map = {"text": "String", "long": "Long", "boolean": "Boolean", "float": "Float", "date": "String"}


def camel_case(snake_case: str) -> str:
    # if snake_case.endswith('s'):
    #     snake_case = snake_case[:-1]
    return "".join(p.capitalize() for p in snake_case.split('_'))


def print_property_hierarchy(map, indent=0):
    prefix = " " * indent
    for k, v in map.items():
        if 'type' in v:
            value_type = type_map[v['type']]
            # if k.endswith('s'):
            #     value_type=f"List<{value_type}>"
            print(f"{prefix}{k}: {value_type}")
        else:
            value_type = camel_case(k)
            # if k.endswith('s'):
            #     value_type=f"List<{value_type}>"
            print(f"{prefix}{k}: {value_type}")
            print_property_hierarchy(v['properties'], indent=indent + 2)


def process_mapping(index_names: str):
    for index_name in index_names:
        print(f"# {index_name}")
        mapping_url = f"https://annotation.republic-caf.diginfra.org/elasticsearch/{index_name}/_mappings"
        logger.info(f"GET {mapping_url}")
        properties = requests.get(mapping_url).json()[index_name]['mappings']['properties']
        print_property_hierarchy(properties)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Read the mapping of the given ES index and show the defined fields",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("index",
                        help="The name of the index",
                        nargs='+',
                        type=str)

    args = parser.parse_args()

    process_mapping(args.index)
