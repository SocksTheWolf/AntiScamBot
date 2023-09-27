#!/bin/sh
pgrep -f "python3 ./Main.py" | xargs kill
