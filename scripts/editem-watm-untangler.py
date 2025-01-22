#!/usr/bin/env python3
import os

import untanngle.textfabric as tf


def main():
    check_environment_variables()
    config = tf.TFUntangleConfig(
        project_name=os.environ['EDITEM_PROJECT'],
        data_path='/watm',
        export_path=f'/out',
        textrepo_base_uri=os.environ['EDITEM_TEXTREPO_URL'],
        excluded_types=[],
        tier0_type=os.environ['EDITEM_TIER0_TYPE'],
        with_facsimiles=os.environ['EDITEM_WITH_FACSIMILES']
    )
    tf.untangle_tf_export(config)


def check_environment_variables():
    required = ['EDITEM_PROJECT', 'EDITEM_TEXTREPO_URL', 'EDITEM_TIER0_TYPE',
                'EDITEM_WITH_FACSIMILES']
    missing = [ev for ev in required if not ev in os.environ]
    if missing:
        print("missing environment variables; set these first")
        for ev in missing:
            print(f'  {ev}')
        exit(-1)


if __name__ == '__main__':
    main()
