#!/usr/bin/env python3

import yaml

import untanngle.annorepo_tools as ar
import untanngle.textfabric as tf

settings_path = '/editem/settings.yml'
export_path = '/out'
# not used beyond as an example for the step class in editem

def main():
    settings = read_settings()
    config = tf.TFUntangleConfig(
        project_name=settings['project'],
        data_path='/watm',
        export_path=export_path,
        textrepo_base_uri=settings['textrepo'],
        excluded_types=[],
        tier0_type=settings['tier0'],
        with_facsimiles=settings['with_facsimiles']
    )
    tf.untangle_tf_export(config)
    export_to_annorepo(settings['project'], settings['annorepo'])


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


def export_to_annorepo(project: str, annorepo_settings: dict[str, any]):
    ar.upload(
        annorepo_base_url=annorepo_settings['url'],
        container_id=annorepo_settings['container'],
        input_paths=[f"{export_path}/{project}/web-annotations.json"],
        api_key=annorepo_settings['api_key'],
        overwrite_container=True,
        show_progress=False
    )


if __name__ == '__main__':
    main()
