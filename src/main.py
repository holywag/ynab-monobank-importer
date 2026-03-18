#!/usr/bin/env python3

import json
from datetime import datetime

import config
from pipeline import Pipeline

TIMESTAMP_FILE = './config/timestamp.json'

print('Initialization')

ctx = config.load()

# TODO: CLI arg for pipeline selection
pipeline_name = 'daily_import'
steps_cfg = config.load_pipeline(ctx.pipeline_paths[pipeline_name])

print(f'Running pipeline: {pipeline_name}')

pipeline = Pipeline.from_config(steps_cfg, ctx)
pipeline.run()

# Save timestamp for read steps with use_last_import
for step_dict in steps_cfg:
    if 'read' in step_dict:
        tr_cfg = step_dict['read'].get('time_range', {})
        if tr_cfg.get('use_last_import'):
            tz = datetime.fromisoformat(tr_cfg['start']).tzinfo
            timestamp = {'last_import': datetime.now(tz=tz).isoformat()}
            with open(TIMESTAMP_FILE, 'w') as f:
                json.dump(timestamp, f)
            print('Saved import timestamp')

print('Done')
