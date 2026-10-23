#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 device_connector.py install
printf '\n按回车关闭。'
read -r done_line
