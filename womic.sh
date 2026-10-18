#!/bin/bash
# Usage: ./womic.sh <phone IP>          (WiFi)
#        ./womic.sh -b <BT address>     (Bluetooth)
DIR="$(dirname "$(readlink -f "$0")")"
lsmod | grep -q snd_aloop || sudo modprobe snd-aloop || exit 1
if [ "$1" = "-b" ]; then TYPE=Bluetooth; ADDR="$2"; else TYPE=WIFI; ADDR="$1"; fi
[ -z "$ADDR" ] && { echo "Usage: $0 <phone IP>   or   $0 -b <BT address>"; exit 1; }


# snd-aloop forces the second opener to match the first one's buffer size,
# so micclient must open the loopback before the WO-Mic source does.
pkill -f micclient-x86_64.AppImage 2>/dev/null
pactl unload-module module-alsa-source 2>/dev/null
echo "🎤 Connecting to $ADDR ($TYPE)... Ctrl+C to stop"
"$DIR/micclient-x86_64.AppImage" -t "$TYPE" "$ADDR" &
PID=$!
trap 'kill $PID 2>/dev/null; exit' INT TERM
for i in $(seq 30); do
    grep -q RUNNING /proc/asound/Loopback/pcm0p/sub0/status && break
    sleep 0.5
done
pactl load-module module-alsa-source device=hw:Loopback,1,0 source_name=WOMic format=s16le channels=1 rate=48000 tsched=0 source_properties=device.description=WO-Mic >/dev/null
pactl set-default-source WOMic
if grep -q RUNNING /proc/asound/Loopback/pcm0p/sub0/status; then
    echo "✅ Streaming. Pick 'WO-Mic' as the microphone (it's the default)"
else
    echo "⚠️  No audio yet — make sure WO Mic is started on the phone"
fi
wait $PID
