#!/bin/sh
cd ..
python3 -m venv .venv
source .venv/bin/activate
nohup python3 ./Main.py