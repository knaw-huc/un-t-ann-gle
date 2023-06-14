#!/usr/bin/env python3
import csv
import json
from dataclasses import dataclass

from loguru import logger


@dataclass
class ImageSetData:
    inventory_num: int
    inventory_id: str
    manifest: str
    long_name: str


volumes_csv = "data/republic-volumes.csv"
image_sets_json = "data/pim-republic-imagesets.json"


def main():
    with open(image_sets_json) as f:
        images_sets = json.load(f)

    data = []
    for y in range(1700, 1800):
        sets_for_year = [i for i in images_sets if
                         str(y) in i["longName"] and i["uri"].startswith("/data/statengeneraal/")]
        data.extend([as_image_set_data(s) for s in sets_for_year])

    export_to_csv(sorted(data, key=lambda d: d.inventory_id))


def export_to_csv(data):
    logger.info(f"=> {volumes_csv}")
    with open(volumes_csv, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['inventory_id', 'inventory_num', 'long_name', 'manifest'])
        writer.writeheader()
        for d in data:
            writer.writerow(d.__dict__)


def as_image_set_data(s):
    inventory_num = int(s["longName"][:4])
    inventory_id = s["uri"].strip('/').replace('data/statengeneraal/', '').replace('/', '_')
    long_name = s["longName"]
    manifest = s["remoteUri"]
    image_set_data = ImageSetData(inventory_num=inventory_num, inventory_id=inventory_id, long_name=long_name,
                                  manifest=manifest)
    return image_set_data


if __name__ == '__main__':
    main()
