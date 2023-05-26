#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass
from typing import List, Tuple, Set

from untanngle.camel_casing import to_camel_case

EXPORT_FILE = 'republic.jsonld'
NAMESPACE = "republic"


@dataclass(eq=True, frozen=True)
class Field:
    label: str
    type: str


def extract_types(annotations: List[dict]) -> List[str]:
    types = set()
    for a in annotations:
        add_extracted_types(a, types)
    return sorted(types)


def add_extracted_types(d: dict, types: Set[str]):
    for (k, v) in d.items():
        if k == 'type':
            if isinstance(v, str):
                types.add(v)
            elif isinstance(v, list):
                for e in v:
                    types.add(e)
        elif isinstance(v, list):
            for e in v:
                if isinstance(e, dict):
                    add_extracted_types(e, types)
        elif isinstance(v, dict):
            add_extracted_types(v, types)


def extract_custom_fields_and_classes(annotations: List[dict]) -> Tuple[List[Field], List[str]]:
    fields = set()
    classes = set()
    for a in annotations:
        add_extracted_fields_and_classes(a, fields, classes)
    return sorted(fields, key=lambda f: f.label), sorted(classes)


def add_extracted_fields_and_classes(d, fields, classes):
    for (k, v) in d.items():
        label = to_camel_case(k)
        if isinstance(v, str):
            fields.add(Field(label=label, type="xsd:string"))
        elif isinstance(v, bool):
            fields.add(Field(label=label, type="xsd:boolean"))
        elif isinstance(v, int):
            fields.add(Field(label=label, type="xsd:integer"))
        elif isinstance(v, float):
            fields.add(Field(label=label, type="xsd:float"))
        elif isinstance(v, list):
            fields.add(Field(label=label, type="xsd:list"))
            for e in v:
                if isinstance(e, dict):
                    add_extracted_fields_and_classes(e, fields, classes)
        elif isinstance(v, dict):
            classes.add(to_camel_case(k.capitalize()))
            add_extracted_fields_and_classes(v, fields, classes)
        elif v is None:
            pass
        else:
            fields.add(Field(label=k, type=f"unknown:{type(v)}"))


def generate_context_file(input_file: str):
    print(f'> importing {input_file} ...')
    with open(input_file) as f:
        annotations = json.load(f)
    num_annotations = len(annotations)
    print(f'> {num_annotations} annotations loaded')
    base_context = {
        "@context": {
            f"{NAMESPACE}": f"https://humanities.knaw.nl/ns/{NAMESPACE}#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "oa": "http://www.w3.org/ns/oa#",
        }
    }
    for class_type in extract_types(annotations):
        type_name = to_camel_case(class_type.capitalize())
        base_context['@context'][type_name] = f"{NAMESPACE}:{type_name}"

    (fields, classes) = extract_custom_fields_and_classes(annotations)
    for clazz in classes:
        base_context['@context'][clazz] = f"{NAMESPACE}:{clazz}"
    for field in fields:
        base_context['@context'][field.label] = {"@id": f"{NAMESPACE}:{field.label}", "@type": f"{field.type}"}

    with open(EXPORT_FILE, 'w') as f:
        json.dump(obj=base_context, fp=f, indent=2)
    print('> done!')


def main():
    parser = argparse.ArgumentParser(
        description="Generate a json-ld context file from an un-t-ann-gle annotationstore with all the custom fields.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("inputfile",
                        help="The un-t-ann-gle annotationstore file to use",
                        type=str)
    args = parser.parse_args()
    generate_context_file(args.inputfile)


if __name__ == '__main__':
    main()
