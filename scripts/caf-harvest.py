#!/usr/bin/env python3
import argparse
import glob
import json
import os
from datetime import datetime

import requests
from loguru import logger


# for each session in session output_dir, retrieve json data from proper CAF resolutions index
def retrieve_res_json(query_string: str, date_string: str, caf_resolutions_output_dir: str):
    logger.info(f"< {query_string}")
    response = requests.get(query_string)
    file_name = f'{date_string}-resolutions.json'

    out_path = caf_resolutions_output_dir + file_name
    logger.info(f"> {out_path}")
    with open(out_path, 'w') as filehandle:
        json.dump(response.json(), filehandle, indent=4)


def harvest_year(year: str):
    # year to harvest
    harvest_date = datetime.now().strftime("%y%m%d")

    # where to store harvest from CAF sessions index
    # sessions_dump_file = f'sessions-{year}-output-19aug22.json'

    # output directories for session and resolution json_data
    output_dir = f'./out/{harvest_date}/'
    caf_sessions_outputdir = output_dir + f'CAF-sessions-{year}/'
    caf_resolutions_outputdir = output_dir + f'CAF-resolutions-{year}/'
    # pattern to filter session json files generated during the process
    session_file_pattern = caf_sessions_outputdir + f"session-{year}-*"

    # query strings
    session_query = f"https://annotation.republic-caf.diginfra.org/elasticsearch/session_lines/_doc/_search?" \
                    f"q=metadata.session_year:{year}&size=10000"
    res_query_base = 'https://annotation.republic-caf.diginfra.org/elasticsearch/resolutions/_doc/_search?' \
                     'size=1000&track_total_hits=true&q=metadata.session_id:'

    # create output directories if they do not yet exist
    if not os.path.exists(output_dir):
        logger.info(f"creating {output_dir}")
        os.makedirs(output_dir)

    if not os.path.exists(caf_sessions_outputdir):
        logger.info(f"creating {caf_sessions_outputdir}")
        os.makedirs(caf_sessions_outputdir)

    if not os.path.exists(caf_resolutions_outputdir):
        logger.info(f"creating {caf_resolutions_outputdir}")
        os.makedirs(caf_resolutions_outputdir)

    # start with harvesting all required session data from proper CAF session ES index
    logger.info(f"< {session_query}")
    response = requests.get(session_query)

    # with open(sessions_dump_file, 'w') as filehandle:
    #    json.dump(response.json(), filehandle, indent=4)

    # generate separate session json file for each session in the ES response
    for session in response.json()['hits']['hits']:
        file_name = session['_id'] + '.json'
        output_path = caf_sessions_outputdir + file_name
        logger.info(f"> {output_path}")
        with open(output_path, 'w') as filehandle:
            json.dump(session, filehandle, indent=4)
    session_file_names = (f for f in glob.glob(session_file_pattern))
    for n in session_file_names:
        base = os.path.basename(n)
        session_id = os.path.splitext(base)[0]
        retrieve_res_json(f'{res_query_base}{session_id}', session_id, caf_resolutions_outputdir)


def main():
    parser = argparse.ArgumentParser(
        description="Harvest the given year from CAF",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("year",
                        help="The year to harvest from CAF",
                        type=str)
    args = parser.parse_args()
    harvest_year(args.year)


if __name__ == '__main__':
    # harvest from CAF session and resolution indexes
    main()
