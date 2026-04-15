#!/bin/sh
set -eu

pkill -f 'training_app.py' || true
pkill -f 'kws_demo.py' || true
pkill -f '/root/kws-demo/app.py' || true
pkill -f 'game_app.py' || true

sleep 2

ps -ef | grep -E 'training_app.py|kws_demo.py|/root/kws-demo/app.py|game_app.py' | grep -v grep || true
