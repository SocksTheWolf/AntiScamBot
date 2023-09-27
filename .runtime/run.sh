#!/bin/sh
# Remember to run this with nohup!
echo starting bot
pwd | grep -q .runtime
if [ "$?" -eq "0" ]; then
    cd ..
fi
python3 -m venv .venv
source .venv/bin/activate
python3 ./Main.py
