#!/usr/bin/env python3

import config
from pipeline import Pipeline

print('Initialization')

ctx = config.load()

# TODO: CLI arg for pipeline selection
# pipeline_name = 'migrate_to_eur'
# pipeline_name = 'convert_to_uah_by_memo'
# pipeline_name = 'daily_import'
pipeline_name = 'fix_amount'
steps_cfg = config.load_pipeline(ctx.pipeline_paths[pipeline_name])

print(f'Running pipeline: {pipeline_name}')

pipeline = Pipeline.from_config(steps_cfg, ctx)
pipeline.run()

print('Done')
