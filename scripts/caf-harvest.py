#!/usr/bin/env python3
import argparse
import glob
import json
import os
from datetime import datetime

from elasticsearch7.client import Elasticsearch
from loguru import logger

es = Elasticsearch("https://annotation.republic-caf.diginfra.org/elasticsearch")
resolutions_index = "full_resolutions"
session_index = "session_metadata"
textregion_index = "session_text_regions"


# for each session in session output_dir, retrieve json data from proper CAF resolutions index
def retrieve_res_json(session_id: str, caf_resolutions_output_dir: str, session_date: str):
    # session_date = session_id[8:18]
    query = {
        "range": {
            "metadata.session_date": {"gte": session_date, "lte": session_date}
        }
    }
    # ic(query)
    response = es.search(index=resolutions_index, query=query, size=10000)

    file_name = f'{session_id}-resolutions.json'
    out_path = f'{caf_resolutions_output_dir}/{file_name}'
    number_of_resolutions = response["hits"]["total"]["value"]
    if number_of_resolutions > 0:
        logger.info(f"=> {out_path} ({number_of_resolutions:4} resolutions)")
        with open(out_path, 'w') as filehandle:
            json.dump([h['_source'] for h in response['hits']['hits']], filehandle, indent=4)
    else:
        logger.warning(f"no resolutions found for session {session_id}")


def check_result_size(max_hits, response):
    size = len(response.json()['hits']['hits'])
    if size == max_hits:
        logger.warning("max_hits hits found! use search_after")


def harvest_year(year: str):
    harvest_date = datetime.now().strftime("%y%m%d")

    # where to store harvest from CAF sessions index
    # output directories for session and resolution json_data
    output_dir = f'./out/{harvest_date}/{year}'
    caf_sessions_output_dir = f'{output_dir}/sessions'
    caf_resolutions_output_dir = f'{output_dir}/resolutions'

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
    query = {"term": {"metadata.session_year": year}}
    response = es.search(index=session_index, query=query, sort="_id", size=10000)

    # generate separate session json file for each session in the ES response
    date_for_session_id = {}
    for session_hit in response['hits']['hits']:
        session = session_hit['_source']
        session_id = session['id']
        file_name = session_id + '.json'
        date_for_session_id[session_id] = session['metadata']['session_date']
        output_path = f"{caf_sessions_output_dir}/{file_name}"
        logger.info(f"=> {output_path}")
        with open(output_path, 'w') as filehandle:
            json.dump(session, filehandle, indent=4)

    # pattern to filter session json files generated during the process
    session_file_pattern = f"{caf_sessions_output_dir}/session-*.json"
    session_file_names = (f for f in glob.glob(session_file_pattern))
    for n in sorted(session_file_names):
        base = os.path.basename(n)
        session_id = os.path.splitext(base)[0]
        retrieve_res_json(session_id, caf_resolutions_output_dir, date_for_session_id[session_id])


def all_years():
    aggs = {
        "min_session_date": {"min": {"field": "metadata.session_date"}},
        "max_session_date": {"max": {"field": "metadata.session_date"}}
    }
    resp = es.search(index=resolutions_index, aggs=aggs, size=0)
    min_session_date = resp["aggregations"]["min_session_date"]["value_as_string"][:10]
    max_session_date = resp["aggregations"]["max_session_date"]["value_as_string"][:10]
    min_year = int(min_session_date[:4])
    max_year = int(max_session_date[:4])
    return [y for y in range(min_year, max_year)]


@logger.catch
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
