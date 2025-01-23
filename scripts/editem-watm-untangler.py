#!/usr/bin/env python3

import untanngle.textfabric as tf
import yaml
from icecream import ic

settings_path = '/editem/settings.yml'


def main():
    settings = read_settings()
    config = tf.TFUntangleConfig(
        project_name=settings['project'],
        data_path='/watm',
        export_path=f'/out',
        textrepo_base_uri=settings['textrepo'],
        excluded_types=[],
        tier0_type=settings['tier0'],
        with_facsimiles=settings['with_facsimiles']
    )
    tf.untangle_tf_export(config)


required_settings = ['project', 'textrepo', 'tier0', 'with_facsimiles', 'annorepo']
required_annorepo_settings = ['url', 'api_key', 'container']


def read_settings():
    with open(settings_path, "r") as f:
        settings = yaml.safe_load(f)
    if not settings:
        settings = {}
    missing = [s for s in required_settings if s not in settings]
    if 'annorepo' in settings:
        missing_annorepo = [f'annorepo.{s}' for s in required_annorepo_settings if s not in settings['annorepo']]
        missing.extend(missing_annorepo)
    else:
        missing.extend([f'annorepo.{s}' for s in required_annorepo_settings])
    if missing:
        print(f"missing settings in {settings_path}:")
        for s in missing:
            print(f'  {s}')
        exit(-1)
    return settings


if __name__ == '__main__':
    main()
