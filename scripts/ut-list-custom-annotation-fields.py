#!/usr/bin/env python3
import json
import sys
from collections import defaultdict
from pathlib import Path

from jsonpath_ng import parse
from loguru import logger

from untanngle.annotations import recursively_get_fields

anno_jsonld_namespaces = [
    "oa",
    "dc",
    "dcterms",
    "dctypes",
    "foaf",
    "rdf",
    "rdfs",
    "skos",
    "xsd",
    "iana",
    "owl",
    "as",
    "schema"
]

anno_jsonld_types = [
    "Annotation",
    "AnnotationCollection",
    "AnnotationPage",
    "Audience",
    "Audio",
    "Choice",
    "CssSelector",
    "CssStylesheet",
    "DataPositionSelector",
    "Dataset",
    "FragmentSelector",
    "HttpRequestState",
    "Image",
    "Motivation",
    "Organization",
    "Person",
    "RangeSelector",
    "ResourceSelection",
    "Software",
    "SpecificResource",
    "SvgSelector",
    "Text",
    "TextPositionSelector",
    "TextQuoteSelector",
    "TextualBody",
    "TimeState",
    "Video",
    "XPathSelector"
]
anno_jsonld_vocab_fields = [
    "motivation",
    "purpose",
    "textDirection"
]
anno_jsonld_fields = [
    "Annotation",
    "AnnotationCollection",
    "AnnotationPage",
    "Audience",
    "Audio",
    "Choice",
    "CssSelector",
    "CssStylesheet",
    "DataPositionSelector",
    "Dataset",
    "FragmentSelector",
    "HttpRequestState",
    "Image",
    "Motivation",
    "Organization",
    "Person",
    "RangeSelector",
    "ResourceSelection",
    "Software",
    "SpecificResource",
    "SvgSelector",
    "Text",
    "TextPositionSelector",
    "TextQuoteSelector",
    "TextualBody",
    "TimeState",
    "Video",
    "XPathSelector",
    "accessibility",
    "assessing",
    "audience",
    "auto",
    "body",
    "bodyValue",
    "bookmarking",
    "cached",
    "canonical",
    "classifying",
    "commenting",
    "conformsTo",
    "created",
    "creator",
    "describing",
    "editing",
    "email",
    "email_sha1",
    "end",
    "endSelector",
    "exact",
    "first",
    "foaf",
    "format",
    "generated",
    "generator",
    "highlighting",
    "homepage",
    "id",
    "identifying",
    "items",
    "label",
    "language",
    "last",
    "linking",
    "ltr",
    "moderating",
    "modified",
    "motivation",
    "name",
    "next",
    "nickname",
    "partOf",
    "prefix",
    "prev",
    "processingLanguage",
    "purpose",
    "questioning",
    "refinedBy",
    "renderedVia",
    "replying",
    "reviewing",
    "rights",
    "rtl",
    "scope",
    "selector",
    "source",
    "sourceDate",
    "sourceDateEnd",
    "sourceDateStart",
    "start",
    "startIndex",
    "startSelector",
    "state",
    "styleClass",
    "stylesheet",
    "suffix",
    "tagging",
    "target",
    "textDirection",
    "total",
    "type",
    "value",
    "via"
]


@logger.catch()
def main(web_annotations_path: str):
    web_annotations_path = Path(web_annotations_path)
    with web_annotations_path.open() as f:
        web_annotations = json.load(f)
    fields_per_type = defaultdict(set)
    custom_types = set()
    for web_annotation in web_annotations:
        if "type" in web_annotation["body"]:
            atype = web_annotation["body"]["type"]
        else:
            atype = ":untyped"
        fields = extract_custom_fields_and_values(web_annotation)
        if fields:
            fields_per_type[atype].update(fields)
        custom_types.update(extract_custom_types(web_annotation))
    types_for_field = defaultdict(set)
    for atype, fields in fields_per_type.items():
        for field in fields:
            types_for_field[field].add(atype)
    print_md_report(fields_per_type, types_for_field, custom_types)


def print_md_report(fields_per_type, types_for_field, types):
    print("## Project: Israels")
    print()

    print("### Custom Fields, per Annotation Type")
    print()
    print("|type|custom fields|")
    print("|--|--|")
    for atype in sorted(fields_per_type.keys()):
        print(f"|{atype} | " + ", ".join(sorted(fields_per_type[atype])) + "|")

    print()
    print("### Annotation Types using custom fields")
    print()

    print("|field|in types|")
    print("|--|--|")
    for field in sorted(types_for_field.keys()):
        print(f"|{field} | " + ", ".join(sorted(types_for_field[field])) + "|")

    print()
    print("### Custom types")
    print()
    for custom_type in sorted(types):
        print("- " + custom_type)
    print()


def extract_custom_fields_and_values(web_annotation):
    return [f for f in recursively_get_fields(web_annotation)
            if not f in anno_jsonld_fields and not f.startswith("@") and not f == 'metadata']


def extract_custom_types(web_annotation):
    jsonpath_expression = parse('$..type')
    matches = jsonpath_expression.find(web_annotation)
    return [m.value for m in matches if
            m.value not in anno_jsonld_types and not m.value.startswith("tt:") and not m.value.endswith("Metadata:")]


if __name__ == '__main__':
    main(sys.argv[1])

# projects:
# - republic
# - globalise

# - israels
# - mondriaan
# - vangogh
# - suriano
# - translatin
# - vangogh
