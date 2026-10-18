#!/usr/bin/env python3
"""WO Mic Client - Qt front-end for the official Linux micclient."""
import os
import re
import subprocess
import sys

from PyQt6.QtCore import QProcess, QSettings, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QRadioButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

DIR = os.path.dirname(os.path.realpath(__file__))
MICCLIENT = os.path.join(DIR, "micclient-x86_64.AppImage")
PLAYBACK_STATUS = "/proc/asound/Loopback/pcm0p/sub0/status"
SOURCE_ARGS = ("module-alsa-source device=hw:Loopback,1,0 source_name=WOMic "
               "format=s16le channels=1 rate=48000 tsched=0 "
               "source_properties=device.description=WO-Mic").split()

BLUETOOTH, USB, WIFI, WIFI_DIRECT = range(4)
TRANSPORT_NAMES = ["Bluetooth", "USB", "Wi-Fi", "Wi-Fi Direct"]


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def paired_bluetooth_devices():
    """Return [(address, name)] of paired devices, or [] if Bluetooth is off."""
    if "Powered: yes" not in run("bluetoothctl", "show"):
        return []
    out = run("bluetoothctl", "devices", "Paired") or run("bluetoothctl", "paired-devices")
    return re.findall(r"Device ([0-9A-F:]{17}) (.+)", out)


def loopback_streaming():
    try:
        with open(PLAYBACK_STATUS) as f:
            return "RUNNING" in f.read()
    except OSError:
        return False


def tips(*lines):
    label = QLabel("Tips:\n\n" + "\n\n".join(f"{i}. {t}" for i, t in enumerate(lines, 1)))
    label.setWordWrap(True)
    return label


class ConnectDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Connect")
        self.resize(750, 370)

        self.group = QButtonGroup(self)
        transport_box = QGroupBox("Transport type")
        tl = QVBoxLayout(transport_box)
        for i, name in enumerate(TRANSPORT_NAMES):
            rb = QRadioButton(name)
            self.group.addButton(rb, i)
            tl.addWidget(rb)
        tl.addStretch()
        transport_box.setFixedWidth(150)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._bluetooth_page())
        self.stack.addWidget(self._usb_page())
        self.stack.addWidget(self._wifi_page())
        self.stack.addWidget(self._wifi_direct_page())
        details_box = QGroupBox("Details")
        QVBoxLayout(details_box).addWidget(self.stack)

        top = QHBoxLayout()
        top.addWidget(transport_box)
        top.addWidget(details_box, 1)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        for b in (self.connect_btn, cancel_btn):
            b.setFixedWidth(150)
        self.connect_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.connect_btn)
        buttons.addSpacing(30)
        buttons.addWidget(cancel_btn)
        buttons.addStretch()

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        layout = QVBoxLayout(self)
        layout.addLayout(top, 1)
        layout.addWidget(line)
        layout.addLayout(buttons)

        self.group.idToggled.connect(self._transport_changed)
        self.group.button(int(settings.value("transport", WIFI))).setChecked(True)

    def _bluetooth_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        self.bt_combo = QComboBox()
        self.bt_status = QLabel()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_bluetooth)
        row = QHBoxLayout()
        row.addWidget(self.bt_combo, 1)
        row.addWidget(refresh)
        v.addLayout(row)
        v.addWidget(self.bt_status)
        v.addSpacing(20)
        v.addWidget(tips("Turn on Bluetooth on phone and PC.",
                         "Pair phone and PC if you have not.",
                         "Select Bluetooth as transport on phone and start the server.",
                         "Select phone as target device in above drop box."))
        v.addStretch()
        return page

    def _usb_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(QLabel("USB transport is not supported by the Linux client."))
        v.addSpacing(20)
        v.addWidget(tips("Use Wi-Fi or Bluetooth instead.",
                         "Tip: USB tethering on the phone creates a network you can use with Wi-Fi mode."))
        v.addStretch()
        return page

    def _ip_page(self, attr, default, tip_lines):
        page = QWidget()
        v = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Phone IP address:"))
        edit = QLineEdit(self.settings.value(attr, default))
        edit.setPlaceholderText("e.g. 192.168.1.6")
        setattr(self, attr, edit)
        row.addWidget(edit, 1)
        v.addLayout(row)
        v.addSpacing(20)
        v.addWidget(tips(*tip_lines))
        v.addStretch()
        return page

    def _wifi_page(self):
        return self._ip_page("wifi_ip", "", [
            "Connect phone and PC to the same Wi-Fi network.",
            "Select Wi-Fi as transport on phone and start the server.",
            "Enter the IP address shown on the phone above."])

    def _wifi_direct_page(self):
        return self._ip_page("wifi_direct_ip", "192.168.43.1", [
            "Turn on the Wi-Fi hotspot on the phone and connect the PC to it.",
            "Select Wi-Fi Direct as transport on phone and start the server.",
            "Enter the IP address shown on the phone above."])

    def _refresh_bluetooth(self):
        self.bt_combo.clear()
        devices = paired_bluetooth_devices()
        for addr, name in devices:
            self.bt_combo.addItem(f"{name} ({addr})", addr)
        last = self.settings.value("bt_addr", "")
        idx = self.bt_combo.findData(last)
        if idx >= 0:
            self.bt_combo.setCurrentIndex(idx)
        self.bt_status.setText("" if devices else "Bluetooth is off or no paired devices")
        self._update_connect_enabled()

    def _transport_changed(self, tid, checked):
        if not checked:
            return
        self.stack.setCurrentIndex(tid)
        if tid == BLUETOOTH:
            self._refresh_bluetooth()
        self._update_connect_enabled()

    def _update_connect_enabled(self):
        tid = self.group.checkedId()
        ok = tid != USB and not (tid == BLUETOOTH and self.bt_combo.count() == 0)
        self.connect_btn.setEnabled(ok)

    def result_target(self):
        """Return (transport id, micclient type, address)."""
        tid = self.group.checkedId()
        self.settings.setValue("transport", tid)
        if tid == BLUETOOTH:
            addr = self.bt_combo.currentData()
            self.settings.setValue("bt_addr", addr)
            return tid, "Bluetooth", addr
        edit = self.wifi_ip if tid == WIFI else self.wifi_direct_ip
        addr = edit.text().strip()
        self.settings.setValue("wifi_ip" if tid == WIFI else "wifi_direct_ip", addr)
        return tid, "WIFI", addr


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("womiclinux", "womic_gui")
        self.setWindowTitle("WO Mic Client")
        self.setWindowIcon(QIcon.fromTheme("audio-input-microphone"))
        self.resize(1070, 650)

        self.message = QLabel("Use Connection > Connect to start.")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setStyleSheet("color: gray; font-size: 15px;")
        self.setCentralWidget(self.message)

        self.proc = None
        self.wait_ticks = 0
        self.poll = QTimer(self, interval=500, timeout=self._poll_stream)

        self._build_menus()
        self._build_statusbar()
        self._set_state("Disconnected")

    def _build_menus(self):
        bar = self.menuBar()
        conn = bar.addMenu("Connection")
        self.act_connect = QAction("Connect...", self, shortcut="Ctrl+N", triggered=self.show_connect)
        self.act_disconnect = QAction("Disconnect", self, shortcut="Ctrl+D", triggered=self.disconnect)
        conn.addActions([self.act_connect, self.act_disconnect])
        conn.addSeparator()
        conn.addAction(QAction("Exit", self, shortcut="Ctrl+Q", triggered=self.close))

        opts = bar.addMenu("Options")
        self.act_default = QAction("Set WO-Mic as default microphone", self, checkable=True)
        self.act_default.setChecked(self.settings.value("set_default", True, type=bool))
        self.act_default.toggled.connect(lambda v: self.settings.setValue("set_default", v))
        opts.addAction(self.act_default)

        help_menu = bar.addMenu("Help")
        help_menu.addAction(QAction("About", self, triggered=lambda: QMessageBox.about(
            self, "About WO Mic Client",
            "Unofficial Qt front-end for the WO Mic Linux client (micclient).\n\n"
            "Audio from the phone appears as the 'WO-Mic' microphone.\n\n"
            "WO Mic and micclient are © Wolicheng Tech. This project is not\n"
            "affiliated with or endorsed by Wolicheng Tech.")))

    def _build_statusbar(self):
        sb = QStatusBar()
        self.state_label = QLabel()
        self.transport_label = QLabel(TRANSPORT_NAMES[int(self.settings.value("transport", WIFI))])
        self.extra_label = QLabel()
        for lbl, w in ((self.state_label, 300), (self.transport_label, 200)):
            lbl.setFrameShape(QFrame.Shape.Panel)
            lbl.setFrameShadow(QFrame.Shadow.Sunken)
            lbl.setFixedWidth(w)
            sb.addWidget(lbl)
        self.extra_label.setFrameShape(QFrame.Shape.Panel)
        self.extra_label.setFrameShadow(QFrame.Shadow.Sunken)
        sb.addWidget(self.extra_label, 1)
        self.setStatusBar(sb)

    def _set_state(self, state, extra=""):
        self.state_label.setText(state)
        self.extra_label.setText(extra)
        connected = self.proc is not None
        self.act_connect.setEnabled(not connected)
        self.act_disconnect.setEnabled(connected)

    def show_connect(self):
        dlg = ConnectDialog(self, self.settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        tid, mtype, addr = dlg.result_target()
        if not addr:
            QMessageBox.warning(self, "WO Mic Client", "Please enter an address.")
            return
        self.start(tid, mtype, addr)

    def start(self, tid, mtype, addr):
        if not os.path.exists(MICCLIENT):
            QMessageBox.critical(self, "WO Mic Client",
                                 f"micclient not found at:\n{MICCLIENT}\n\nRun ./install.sh first.")
            return
        if not os.path.exists("/proc/asound/Loopback"):
            subprocess.run(["pkexec", "modprobe", "snd-aloop"])
            if not os.path.exists("/proc/asound/Loopback"):
                QMessageBox.critical(self, "WO Mic Client",
                                     "The snd-aloop kernel module is not loaded.\nRun ./setup.sh once.")
                return
        self.transport_label.setText(TRANSPORT_NAMES[tid])
        # snd-aloop makes the second opener match the first one's buffer size,
        # so micclient must open the loopback before the WO-Mic source does.
        run("pkill", "-f", "micclient-x86_64.AppImage")
        run("pactl", "unload-module", "module-alsa-source")

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read_output)
        self.proc.finished.connect(self._finished)
        self.proc.start(MICCLIENT, ["-t", mtype, addr])
        self.wait_ticks = 0
        self.poll.start()
        self.message.setText(f"Connecting to {addr}...")
        self._set_state("Connecting...", addr)

    def _read_output(self):
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace").strip()
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith("ALSA lib")]
        if lines:
            self.extra_label.setText(lines[-1])

    def _load_source(self):
        if "WOMic" not in run("pactl", "list", "short", "sources"):
            run("pactl", "load-module", *SOURCE_ARGS)
        if self.act_default.isChecked():
            run("pactl", "set-default-source", "WOMic")

    def _poll_stream(self):
        self.wait_ticks += 1
        if loopback_streaming():
            self.poll.stop()
            self._load_source()
            self._set_state("Connected", self.extra_label.text())
            self.message.setText("🎤  Streaming — use 'WO-Mic' as your microphone")
        elif self.wait_ticks > 30:
            self.poll.stop()
            self._load_source()
            self.message.setText("Connected but no audio yet.\nMake sure WO Mic is started on the phone.")

    def _finished(self):
        self.poll.stop()
        last = self.extra_label.text()
        self.proc = None
        self._load_source()
        self._set_state("Disconnected", last)
        self.message.setText("Disconnected.\nIf connecting failed, press Stop then Start on the phone and try again.")

    def disconnect(self):
        if self.proc:
            self.proc.finished.disconnect()
            self.proc.kill()
            self.proc.waitForFinished(2000)
            self.proc = None
        self.poll.stop()
        self._set_state("Disconnected")
        self.message.setText("Use Connection > Connect to start.")

    def closeEvent(self, event):
        self.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WO Mic Client")
    win = MainWindow()
    win.show()
    QTimer.singleShot(0, win.show_connect)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
