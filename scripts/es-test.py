#!/usr/bin/env python3

from elasticsearch7 import Elasticsearch
from icecream import ic
from loguru import logger


@logger.catch
def main():
    es = Elasticsearch("https://annotation.republic-caf.diginfra.org/elasticsearch")

    query = {
        "match": {
            "metadata.session_id": "session-1728-11-17-ordinaris-num-1"
        }
    }
    # do_query(es, query)

    query = {
        "range": {
            "metadata.session_date": {"gte": "1704-01-01", "lt": "1705-01-02"}
        }
    }
    # do_query(es, query)

    aggs = {
        "min_session_date": {"min": {"field": "metadata.session_date"}},
        "max_session_date": {"max": {"field": "metadata.session_date"}}
    }
    resp = es.search(index="resolutions", aggs=aggs, size=0)
    min_session_date = resp["aggregations"]["min_session_date"]["value_as_string"][:10]
    max_session_date = resp["aggregations"]["max_session_date"]["value_as_string"][:10]
    ic(min_session_date, max_session_date)
    min_year = int(min_session_date[:4])
    max_year = int(max_session_date[:4])
    ic(min_year, max_year)
    max_resolutions = 0
    for year in range(min_year, max_year):
        query = {
            "range": {
                "metadata.session_date": {"gte": f"{year}-01-01", "lt": f"{year + 1}-01-01"}
            }
        }
        resp = es.search(index="resolutions", query=query, size=0)
        total = resp["hits"]["total"]["value"]
        max_resolutions = max(max_resolutions, total)
        print(f"{year} : {total}")
    ic(max_resolutions)
    # print(json.dumps(resp, indent=2))
    # process_response(resp)


# 1705-01-01
# 1796-03-08

def do_query(es, query):
    resp = es.search(index="resolutions", query=query, size=100)
    process_response(resp)


def process_response(resp):
    print(f"Got {resp['hits']['total']['value']:d} Hits:")
    # print(json.dumps(resp, indent=2))
    max_score = resp['hits']['max_score']
    for hit in resp['hits']['hits']:
        score = hit["_score"]
        session_id = hit["_source"]["metadata"]["session_id"]
        x = "X" if score == max_score else ""
        print(f"{session_id} | {score} | {x}")


if __name__ == '__main__':
    main()
