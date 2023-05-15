#!/usr/bin/env python3
import argparse

from icecream import ic
from loguru import logger
from untanngle.provenance import ProvenanceClient, ProvenanceData


@logger.catch()
def main():
    parser = argparse.ArgumentParser(
        description="Post a provenance to the given provenance server, using the given api-key",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-p",
                        "--provenance-base-url",
                        required=True,
                        help="The base URL of the provenance server.",
                        type=str,
                        metavar="provenance_base_url")
    parser.add_argument("-k",
                        "--api-key",
                        required=True,
                        help="The api-key to get access to the provenance server api",
                        type=str,
                        metavar="api_key")
    args = parser.parse_args()
    base_url = trim_trailing_slash(args.provenance_base_url)
    post_provenance(base_url, args.api_key)


def post_provenance(base_url: str, api_key: str):
    pc = ProvenanceClient(base_url, api_key)
    pd = ProvenanceData(
        who='orcid:12345',
        where='http://somelocation.uri',
        when='2022-02-02T02:00:00Z',
        how_software='https://github.com/knaw-huc/provenance/commit/b725d0a592961985f0510afed1bc98d118acb32f',
        how_init='-i my-data.trig -o my-output.csv',
        why='Motivation',
        source=['md5:7815696ecbf1c96e6894b779456d330e', 'file:my-data.trig'],
        source_rel=['primary', 'primary'],
        target=['file:my-output.csv'],
        target_rel=['primary']
    )
    ic(pd)
    j = pd.to_json()
    ic(j)
    id = pc.add_provenance(pd)
    ic(id)


def trim_trailing_slash(url: str):
    if url.endswith('/'):
        return url[0:-1]
    else:
        return url


if __name__ == '__main__':
    main()
