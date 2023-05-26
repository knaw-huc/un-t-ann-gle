# harvest from CAF session and resolution indexes

import glob
import json
import os

import requests

# year to harvest
year = 1728

# where to store harvest from CAF sessions index
# sessions_dump_file = f'sessions-{year}-output-19aug22.json'

# output directories for session and resolution json_data
output_dir = 'output-230315/'
caf_sessions_outputdir = output_dir + f'CAF-sessions-{year}/'
caf_resolutions_outputdir = output_dir + f'CAF-resolutions-{year}/'

# pattern to filter session json files generated during the process
session_file_pattern = caf_sessions_outputdir + f"session-{year}-*"

# query strings
session_query = f"https://annotation.republic-caf.diginfra.org/elasticsearch/session_lines/_doc/_search?q=metadata.session_year:{year}&size=10000"
res_query_base = 'https://annotation.republic-caf.diginfra.org/elasticsearch/resolutions/_doc/_search?size=1000&track_total_hits=true&q=metadata.session_id:'

# create output directories if they do not yet exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

if not os.path.exists(caf_sessions_outputdir):
    os.makedirs(caf_sessions_outputdir)

if not os.path.exists(caf_resolutions_outputdir):
    os.makedirs(caf_resolutions_outputdir)

# start with harvesting all required session data from proper CAF session ES index
print(session_query)
response = requests.get(session_query)

# with open(sessions_dump_file, 'w') as filehandle:
#    json.dump(response.json(), filehandle, indent=4)

# generate separate session json file for each session in the ES response    
for session in response.json()['hits']['hits']:
    file_name = session['_id'] + '.json'
    with open(caf_sessions_outputdir + file_name, 'w') as filehandle:
        json.dump(session, filehandle, indent=4)


# for each session in session output_dir, retrieve json data from proper CAF resolutions index
def retrieve_res_json(query_string, date_string):
    print(query_string)
    response = requests.get(query_string)
    file_name = date_string + '-resolutions.json'

    with open(caf_resolutions_outputdir + file_name, 'w') as filehandle:
        json.dump(response.json(), filehandle, indent=4)


session_file_names = (f for f in glob.glob(session_file_pattern))
for n in session_file_names:
    base = os.path.basename(n)
    session_id = os.path.splitext(base)[0]
    retrieve_res_json(res_query_base + f'{session_id}', session_id)
