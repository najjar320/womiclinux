#!/bin/bash
# Remove everything install.sh added
pkill -f micclient-x86_64.AppImage 2>/dev/null
pactl unload-module module-alsa-source 2>/dev/null
rm -rf "$HOME/.local/share/womic-linux"
rm -f "$HOME/.local/bin/womic" "$HOME/.local/bin/womic-gui" \
      "$HOME/.local/share/applications/womic.desktop" \
      "$HOME/.config/pipewire/pipewire-pulse.conf.d/womic.conf"
sudo rm -f /etc/modules-load.d/snd-aloop.conf
echo "✔ Uninstalled. (python3-pyqt6 was left installed.)"
