#!/usr/bin/env python3

import config
from pipeline import Pipeline

print('Initialization')

ctx = config.load()

# TODO: CLI arg for pipeline selection
pipeline_name = 'daily_import'
steps_cfg = config.load_pipeline(ctx.pipeline_paths[pipeline_name])

print(f'Running pipeline: {pipeline_name}')

pipeline = Pipeline.from_config(steps_cfg, ctx)
pipeline.run()

print('Done')
