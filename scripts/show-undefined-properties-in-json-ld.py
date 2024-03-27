#!/usr/bin/env python3
import functools
import json
import sys
from typing import Set

import requests
from loguru import logger


class JsonLdContext:

    def __init__(self, defined_properties: Set[str], defined_classes: Set[str]):
        self.defined_properties = defined_properties
        self.defined_classes = defined_classes

    @staticmethod
    @functools.cache
    def from_path(path: str) -> 'JsonLdContext':
        logger.info(f"<= {path}")
        with open(path) as f:
            context = json.load(f)['@context']
        return JsonLdContext._from_context_dict(context)

    @staticmethod
    def _from_context_dict(context):
        defined_properties = {k for k in context.keys() if k[:1].islower()}
        defined_classes = {k for k in context.keys() if k[:1].isupper()}
        return JsonLdContext(defined_properties=defined_properties, defined_classes=defined_classes)

    @staticmethod
    @functools.cache
    def from_url(url: str) -> 'JsonLdContext':
        logger.info(f"GET {url}")
        response = requests.get(url)
        context = response.json()['@context']
        return JsonLdContext._from_context_dict(context)


def get_property_set(a_dict: dict) -> Set[str]:
    props = set()
    for key in [k for k in a_dict.keys() if not k.startswith('@') and ':' not in k]:
        props.add(key)
        value = a_dict[key]
        if isinstance(value, dict):
            props.update(get_property_set(value))
        elif isinstance(value, list):
            for i in value:
                if isinstance(i, dict):
                    props.update(get_property_set(i))
    return props


def get_defined_props(context_list) -> Set[str]:
    if isinstance(context_list, str):
        return JsonLdContext.from_url(context_list).defined_properties
    elif isinstance(context_list, list):
        props = set()
        for item in context_list:
            if isinstance(item, str):
                props.update(JsonLdContext.from_url(item).defined_properties)
        return props

    # republic_props = JsonLdContext.from_path(
    #     "/Users/bram/workspaces/namespaces/namespaces-huc/republic.jsonld").defined_properties
    # anno_props = JsonLdContext.from_path(
    #     "/Users/bram/workspaces/elucidate/elucidate-server/elucidate-server/src/main/resources/contexts/anno.jsonld").defined_properties
    # return republic_props.union(anno_props)


@logger.catch
def main(path: str):
    logger.info(f"<= {path}")
    with open(path) as f:
        annotations = json.load(f)
    undefined_props = set()
    for anno in annotations:
        defined_props = get_defined_props(anno['@context'])
        props = get_property_set(anno)
        undefined_props.update(props - defined_props)
    print(f"# undefined properties found:")
    for p in sorted(list(undefined_props)):
        print(f"{p}: republic:{p}")


if __name__ == '__main__':
    input_path = sys.argv[1]
    main(input_path)
