#!/bin/bash
nohup python3 app.py -c config.yaml  >> ./alertmanager-webhook.log 2>&1 &
