#!/bin/bash
# WO Mic Linux GUI installer (per-user install, asks for sudo only for system steps)
set -e

APP_DIR="$HOME/.local/share/womic-linux"
BIN_DIR="$HOME/.local/bin"
DESKTOP_FILE="$HOME/.local/share/applications/womic.desktop"
PIPEWIRE_CONF="$HOME/.config/pipewire/pipewire-pulse.conf.d/womic.conf"
APPIMAGE_URL="https://wolicheng.com/womic/softwares/micclient-x86_64.AppImage"
APPIMAGE_SHA256="ea0ec88601d69dcbaa226b94c1f98379f90c116aa9e7edf2fd1247be257e1dbb"
SRC="$(cd "$(dirname "$0")" && pwd)"

step() { echo -e "\n\033[1;34m==>\033[0m $*"; }
die()  { echo -e "\033[1;31mError:\033[0m $*" >&2; exit 1; }

[ "$(uname -m)" = "x86_64" ] || die "micclient only supports x86_64."
command -v pactl >/dev/null || die "pactl not found (PipeWire/PulseAudio is required)."

step "Installing dependencies (python3-pyqt6, curl)"
if ! python3 -c "import PyQt6.QtWidgets" 2>/dev/null || ! command -v curl >/dev/null; then
    if command -v apt-get >/dev/null; then
        sudo apt-get install -y python3-pyqt6 curl
    elif command -v dnf >/dev/null; then
        sudo dnf install -y python3-pyqt6 curl
    elif command -v pacman >/dev/null; then
        sudo pacman -S --needed --noconfirm python-pyqt6 curl
    else
        die "Please install PyQt6 for Python 3 and curl, then re-run."
    fi
fi

step "Getting the official WO Mic client (micclient)"
mkdir -p "$APP_DIR"
APPIMAGE="$APP_DIR/micclient-x86_64.AppImage"
if [ -f "$SRC/micclient-x86_64.AppImage" ]; then
    cp "$SRC/micclient-x86_64.AppImage" "$APPIMAGE"
else
    curl -fL --progress-bar -o "$APPIMAGE" "$APPIMAGE_URL" || die "Download failed: $APPIMAGE_URL"
fi
if ! echo "$APPIMAGE_SHA256  $APPIMAGE" | sha256sum -c --quiet 2>/dev/null; then
    echo "Warning: micclient checksum differs from the tested version (it may have been updated)."
fi
chmod +x "$APPIMAGE"

step "Loading snd-aloop and enabling it at boot"
lsmod | grep -q snd_aloop || sudo modprobe snd-aloop
grep -qx snd-aloop /etc/modules-load.d/snd-aloop.conf 2>/dev/null || echo snd-aloop | sudo tee /etc/modules-load.d/snd-aloop.conf >/dev/null

step "Installing app files"
install -m 755 "$SRC/womic_gui.py" "$SRC/womic.sh" "$APP_DIR/"
mkdir -p "$(dirname "$PIPEWIRE_CONF")" "$BIN_DIR" "$(dirname "$DESKTOP_FILE")"
install -m 644 "$SRC/config/womic-pipewire.conf" "$PIPEWIRE_CONF"
ln -sf "$APP_DIR/womic_gui.py" "$BIN_DIR/womic-gui"
ln -sf "$APP_DIR/womic.sh" "$BIN_DIR/womic"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=WO Mic Client
Comment=Use your phone as a microphone (unofficial GUI for WO Mic)
Exec=$APP_DIR/womic_gui.py
Icon=audio-input-microphone
Type=Application
Categories=AudioVideo;Audio;
Keywords=microphone;mic;phone;womic;
EOF

step "Creating the WO-Mic input device"
pactl list short sources | grep -q WOMic || pactl load-module module-alsa-source \
    device=hw:Loopback,1,0 source_name=WOMic format=s16le channels=1 rate=48000 tsched=0 \
    source_properties=device.description=WO-Mic >/dev/null || true
# Hide the auto-created loopback card profile so apps don't pick the wrong (silent) input
CARD=$(pactl list short cards | awk '/snd_aloop/ {print $2; exit}')
[ -n "$CARD" ] && pactl set-card-profile "$CARD" off || true

echo -e "\n\033[1;32m✔ Installed!\033[0m Launch \"WO Mic Client\" from your app menu, or run: womic-gui"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "  (Add $BIN_DIR to your PATH to use the womic / womic-gui commands.)";; esac
