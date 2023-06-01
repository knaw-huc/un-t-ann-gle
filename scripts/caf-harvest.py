#!/usr/bin/env python3
import argparse
import glob
import json
import os
from datetime import datetime

import requests
from elasticsearch7.client import Elasticsearch
from icecream import ic
from loguru import logger


# for each session in session output_dir, retrieve json data from proper CAF resolutions index
def retrieve_res_json(query_base_url: str, date_string: str, caf_resolutions_output_dir: str):
    # max_hits = requests.get(query_base_url + "&size=1").json()['hits']['total']['value']
    max_hits = 10
    query_base_url = f"{query_base_url}&size={max_hits}"
    logger.info(f"< {query_base_url}")
    response = requests.get(query_base_url)

    file_name = f'{date_string}-resolutions.json'
    out_path = f'{caf_resolutions_output_dir}/{file_name}'
    # check_result_size(max_hits, response)
    logger.info(f"> {out_path}")
    with open(out_path, 'w') as filehandle:
        json.dump(response.json(), filehandle, indent=4)


def check_result_size(max_hits, response):
    size = len(response.json()['hits']['hits'])
    if size == max_hits:
        logger.warning("max_hits hits found! use search_after")


def harvest_year(year: str):
    harvest_date = datetime.now().strftime("%y%m%d")

    # where to store harvest from CAF sessions index
    # output directories for session and resolution json_data
    output_dir = f'./out/{harvest_date}'
    caf_sessions_output_dir = f'{output_dir}/CAF-sessions-{year}'
    caf_resolutions_output_dir = f'{output_dir}/CAF-resolutions-{year}'

    # pattern to filter session json files generated during the process
    session_file_pattern = f"{caf_sessions_output_dir}/session-{year}-*"

    # query strings
    session_query = f"https://annotation.republic-caf.diginfra.org/elasticsearch/session_lines/_doc/_search?" \
                    f"q=metadata.session_year:{year}"
    res_query_base = 'https://annotation.republic-caf.diginfra.org/elasticsearch/resolutions/_doc/_search?' \
                     'track_total_hits=true&q=metadata.session_id:'

    # create output directories if they do not yet exist
    if not os.path.exists(output_dir):
        logger.info(f"creating {output_dir}")
        os.makedirs(output_dir)

    if not os.path.exists(caf_sessions_output_dir):
        logger.info(f"creating {caf_sessions_output_dir}")
        os.makedirs(caf_sessions_output_dir)

    if not os.path.exists(caf_resolutions_output_dir):
        logger.info(f"creating {caf_resolutions_output_dir}")
        os.makedirs(caf_resolutions_output_dir)

    # start with harvesting all required session data from proper CAF session ES index
    max_hits = requests.get(session_query + "&size=1").json()['hits']['total']['value']
    session_query = f'{session_query}&size={max_hits}'
    logger.info(f"< {session_query}")
    response = requests.get(session_query)

    # with open(sessions_dump_file, 'w') as filehandle:
    #    json.dump(response.json(), filehandle, indent=4)

    # generate separate session json file for each session in the ES response
    for session in response.json()['hits']['hits']:
        file_name = session['_id'] + '.json'
        output_path = f"{caf_sessions_output_dir}/{file_name}"
        logger.info(f"> {output_path}")
        with open(output_path, 'w') as filehandle:
            json.dump(session, filehandle, indent=4)
    session_file_names = (f for f in glob.glob(session_file_pattern))
    for n in sorted(session_file_names):
        base = os.path.basename(n)
        session_id = os.path.splitext(base)[0]
        retrieve_res_json(f'{res_query_base}{session_id}', session_id, caf_resolutions_output_dir)


def all_years():
    es = Elasticsearch("https://annotation.republic-caf.diginfra.org/elasticsearch")
    aggs = {
        "min_session_date": {"min": {"field": "metadata.session_date"}},
        "max_session_date": {"max": {"field": "metadata.session_date"}}
    }
    resp = es.search(index="resolutions", aggs=aggs, size=0)
    min_session_date = resp["aggregations"]["min_session_date"]["value_as_string"][:10]
    max_session_date = resp["aggregations"]["max_session_date"]["value_as_string"][:10]
    min_year = int(min_session_date[:4])
    max_year = int(max_session_date[:4])
    return [y for y in range(min_year, max_year)]


def main():
    parser = argparse.ArgumentParser(
        description="Harvest the given year from CAF",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("year",
                        help="The year(s) to harvest from CAF, or \"all\" for all available years",
                        nargs='+',
                        type=str)
    args = parser.parse_args()
    years = args.year
    if 'all' in years:
        years = all_years()
    for year in sorted(years):
        harvest_year(year)


if __name__ == '__main__':
    # harvest from CAF session and resolution indexes
    main()
