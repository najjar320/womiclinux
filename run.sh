#!/bin/bash
# Launch the WO Mic Client GUI
DIR="$(dirname "$(readlink -f "$0")")"
lsmod | grep -q snd_aloop || pkexec modprobe snd-aloop
exec python3 "$DIR/womic_gui.py" "$@"
