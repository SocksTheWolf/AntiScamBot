#!/bin/bash
pwd | grep -q .runtime
if [ "$?" -eq "0" ]; then
    cd ..
fi
python3 -m venv .venv
source .venv/bin/activate
echo "Updating requirements"
python3 -m pip install -r requirements.txt
