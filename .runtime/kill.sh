#!/bin/sh
pgrep -f "python3 ./Main.py" | xargs kill >/dev/null 2>&1
