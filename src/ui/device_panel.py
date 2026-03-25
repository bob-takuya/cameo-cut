"""
Device connection panel for CameoCut

Shows device connection status and provides send functionality.
Supports both USB and Bluetooth connections.
"""

import logging
from typing import Optional, Callable, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QGroupBox, QComboBox,
    QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot

logger = logging.getLogger(__name__)


class CutWorker(QThread):
    """Worker thread for sending cutting jobs to the device.

    Running send_job() on the main thread blocks the UI (cursor freezes).
    This worker moves the blocking I/O off the main thread.
    """

    progress_updated = pyqtSignal(int, int)   # sent_bytes, total_bytes
    finished = pyqtSignal(bool)                # success

    def __init__(self, cameo, job, parent=None):
        super().__init__(parent)
        self._cameo = cameo
        self._job = job

    def run(self):
        def progress_cb(sent: int, total: int):
            self.progress_updated.emit(sent, total)

        try:
            success = self._cameo.send_job(self._job, progress_cb)
        except Exception as e:
            logger.error(f"CutWorker error: {e}")
            success = False
        self.finished.emit(success)

from device.cameo import Cameo5, CameoState, CuttingJob, ConnectionType
from gpgl.protocol import DeviceStatus


class BluetoothScanDialog(QDialog):
    """Dialog for scanning and selecting Bluetooth devices"""

    device_selected = pyqtSignal(str, str)  # address, name

    def __init__(self, cameo: Cameo5, parent=None):
        super().__init__(parent)
        self._cameo = cameo
        self._devices: List[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Bluetooth Devices")
        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel("Click Scan to search for devices...")
        layout.addWidget(self.status_label)

        # Device list
        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.device_list)

        # Buttons
        button_layout = QHBoxLayout()

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self._scan)
        button_layout.addWidget(self.scan_btn)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self._connect_selected)
        button_layout.addWidget(self.connect_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        # Connect list selection
        self.device_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _scan(self):
        """Scan for Bluetooth devices"""
        self.scan_btn.setEnabled(False)
        self.status_label.setText("Scanning for Cameo devices...")
        self.device_list.clear()

        # Scan (this may take a few seconds)
        QTimer.singleShot(100, self._do_scan)

    def _do_scan(self):
        """Perform the actual scan"""
        self._devices = self._cameo.scan_bluetooth(timeout=5.0)

        self.device_list.clear()

        if self._devices:
            for device in self._devices:
                name = device.get('name', 'Unknown')
                address = device.get('address', '')
                rssi = device.get('rssi', 0)

                item = QListWidgetItem(f"{name} ({address}) [{rssi} dBm]")
                item.setData(Qt.ItemDataRole.UserRole, address)
                self.device_list.addItem(item)

            self.status_label.setText(f"Found {len(self._devices)} device(s)")
        else:
            self.status_label.setText("No Cameo devices found. Make sure Bluetooth is enabled on your Cameo.")

        self.scan_btn.setEnabled(True)

    def _on_selection_changed(self):
        """Handle device selection change"""
        self.connect_btn.setEnabled(len(self.device_list.selectedItems()) > 0)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on device"""
        self._connect_selected()

    def _connect_selected(self):
        """Connect to selected device"""
        items = self.device_list.selectedItems()
        if not items:
            return

        address = items[0].data(Qt.ItemDataRole.UserRole)
        name = items[0].text().split(" (")[0]

        self.device_selected.emit(address, name)
        self.accept()


class DevicePanel(QWidget):
    """Panel for device connection and control"""

    # Signals
    connection_changed = pyqtSignal(bool)
    job_started = pyqtSignal()
    job_completed = pyqtSignal(bool)  # success

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cameo: Optional[Cameo5] = None
        self._pending_job: Optional[CuttingJob] = None
        self._cut_worker: Optional[CutWorker] = None
        self._setup_ui()
        self._setup_refresh_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Device group
        group = QGroupBox("Device")
        group_layout = QVBoxLayout(group)

        # Connection status
        status_layout = QHBoxLayout()
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #888; font-size: 16px;")
        status_layout.addWidget(self.status_indicator)

        self.status_label = QLabel("Not connected")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        group_layout.addLayout(status_layout)

        # Device info
        self.device_info = QLabel("")
        self.device_info.setStyleSheet("color: #888; font-size: 11px;")
        group_layout.addWidget(self.device_info)

        # Connection type label
        self.connection_type_label = QLabel("")
        self.connection_type_label.setStyleSheet("color: #666; font-size: 10px;")
        group_layout.addWidget(self.connection_type_label)

        # Connect buttons
        button_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        button_layout.addWidget(self.connect_btn)

        self.bluetooth_btn = QPushButton("Bluetooth...")
        self.bluetooth_btn.clicked.connect(self._on_bluetooth_clicked)
        button_layout.addWidget(self.bluetooth_btn)

        group_layout.addLayout(button_layout)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self._refresh_status)
        self.refresh_btn.setEnabled(False)
        group_layout.addWidget(self.refresh_btn)

        layout.addWidget(group)

        # Send group
        send_group = QGroupBox("Send to Cutter")
        send_layout = QVBoxLayout(send_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        send_layout.addWidget(self.progress_bar)

        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send_clicked)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #888;
            }
            QPushButton:hover:enabled {
                background-color: #1976D2;
            }
        """)
        send_layout.addWidget(self.send_btn)

        # Test cut button
        self.test_btn = QPushButton("Test Cut")
        self.test_btn.setEnabled(False)
        self.test_btn.clicked.connect(self._on_test_clicked)
        send_layout.addWidget(self.test_btn)

        # ── Home / Load / Unload ──────────────────────────────────────
        media_layout = QHBoxLayout()

        self.home_btn = QPushButton("🏠 Home")
        self.home_btn.setEnabled(False)
        self.home_btn.setToolTip("キャリッジをホーム位置に戻す (H コマンド)")
        self.home_btn.clicked.connect(self._on_home_clicked)
        self.home_btn.setStyleSheet("""
            QPushButton { padding: 6px; border-radius: 4px; }
            QPushButton:disabled { color: #888; }
        """)
        media_layout.addWidget(self.home_btn)

        self.load_btn = QPushButton("⬇ Load")
        self.load_btn.setEnabled(False)
        self.load_btn.setToolTip("カッティングマットを引き込む (FF1 コマンド)")
        self.load_btn.clicked.connect(self._on_load_clicked)
        self.load_btn.setStyleSheet("""
            QPushButton { padding: 6px; border-radius: 4px; }
            QPushButton:disabled { color: #888; }
        """)
        media_layout.addWidget(self.load_btn)

        self.unload_btn = QPushButton("⬆ Unload")
        self.unload_btn.setEnabled(False)
        self.unload_btn.setToolTip("カッティングマットを排出する (FF0 コマンド)")
        self.unload_btn.clicked.connect(self._on_unload_clicked)
        self.unload_btn.setStyleSheet("""
            QPushButton { padding: 6px; border-radius: 4px; }
            QPushButton:disabled { color: #888; }
        """)
        media_layout.addWidget(self.unload_btn)

        send_layout.addLayout(media_layout)

        # Stop/Resume buttons
        stop_resume_layout = QHBoxLayout()

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        stop_resume_layout.addWidget(self.stop_btn)

        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_resume_clicked)
        self.resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        stop_resume_layout.addWidget(self.resume_btn)

        send_layout.addLayout(stop_resume_layout)

        # Device status label
        self.device_state_label = QLabel("Status: --")
        self.device_state_label.setStyleSheet("color: #888; font-size: 11px;")
        send_layout.addWidget(self.device_state_label)

        layout.addWidget(send_group)
        layout.addStretch()

        # Track if device was stopped by user
        self._device_stopped = False

    def _setup_refresh_timer(self):
        """Setup timer to refresh device status"""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.setInterval(2000)  # 2 seconds

    def initialize(self):
        """Initialize the device controller"""
        self._cameo = Cameo5()
        self._cameo.add_status_listener(self._on_status_change)

    def _on_connect_clicked(self):
        """Handle connect button click (USB/Auto)"""
        if self._cameo is None:
            self.initialize()

        if self._cameo.is_connected:
            self._disconnect()
        else:
            self._connect()

    def _on_bluetooth_clicked(self):
        """Handle Bluetooth button click"""
        if self._cameo is None:
            self.initialize()

        if self._cameo.is_connected:
            self._disconnect()

        # Show Bluetooth scan dialog
        dialog = BluetoothScanDialog(self._cameo, self)
        dialog.device_selected.connect(self._connect_bluetooth)
        dialog.exec()

    def _connect(self):
        """Connect to the device (USB first, then Bluetooth)"""
        self.connect_btn.setEnabled(False)
        self.bluetooth_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        self.status_label.setText("Searching for Cameo (USB)...")

        # Try USB first
        QTimer.singleShot(100, self._try_connect)

    def _try_connect(self):
        """Try to connect via USB"""
        success = self._cameo.connect_usb()

        if success:
            self._on_connected()
        else:
            self.connect_btn.setText("Connect")
            self.status_label.setText("USB not found")
            self.device_info.setText("Use 'Bluetooth...' to connect via Bluetooth")
            self.status_indicator.setStyleSheet("color: #FF9800; font-size: 16px;")

        self.connect_btn.setEnabled(True)
        self.bluetooth_btn.setEnabled(True)

    def _connect_bluetooth(self, address: str, name: str):
        """Connect to a Bluetooth device"""
        self.connect_btn.setEnabled(False)
        self.bluetooth_btn.setEnabled(False)
        self.status_label.setText(f"Connecting to {name}...")

        # Connect
        QTimer.singleShot(100, lambda: self._do_bluetooth_connect(address))

    def _do_bluetooth_connect(self, address: str):
        """Perform Bluetooth connection"""
        success = self._cameo.connect_bluetooth(address)

        if success:
            self._on_connected()
        else:
            self.status_label.setText("Bluetooth connection failed")
            self.device_info.setText("Try turning Bluetooth off and on again")
            self.status_indicator.setStyleSheet("color: #F44336; font-size: 16px;")

        self.connect_btn.setEnabled(True)
        self.bluetooth_btn.setEnabled(True)

    def _on_connected(self):
        """Handle successful connection"""
        self.connect_btn.setText("Disconnect")
        self.refresh_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self.home_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self.unload_btn.setEnabled(True)
        self._refresh_timer.start()
        self.connection_changed.emit(True)

        # Show connection type
        if self._cameo.connection_type == ConnectionType.USB:
            self.connection_type_label.setText("Connected via USB")
        elif self._cameo.connection_type == ConnectionType.BLUETOOTH:
            self.connection_type_label.setText("Connected via Bluetooth")

    def _disconnect(self):
        """Disconnect from the device"""
        if self._cameo:
            self._cameo.disconnect()

        self._refresh_timer.stop()
        self.connect_btn.setText("Connect")
        self.refresh_btn.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.home_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.unload_btn.setEnabled(False)
        self.status_label.setText("Not connected")
        self.status_indicator.setStyleSheet("color: #888; font-size: 16px;")
        self.device_info.setText("")
        self.connection_type_label.setText("")
        self.connection_changed.emit(False)

    def _on_status_change(self, state: CameoState):
        """Handle device status change"""
        if state.connected:
            self.status_label.setText(state.device_name)
            self.device_info.setText(f"Firmware: {state.firmware_version}")

            if state.status == DeviceStatus.READY:
                self.status_indicator.setStyleSheet("color: #4CAF50; font-size: 16px;")
                self.device_state_label.setText("Status: Ready")
                self.stop_btn.setEnabled(False)
                self.resume_btn.setEnabled(self._device_stopped)
            elif state.status == DeviceStatus.MOVING:
                self.status_indicator.setStyleSheet("color: #FFC107; font-size: 16px;")
                self.device_state_label.setText("Status: Moving...")
                self.stop_btn.setEnabled(True)
                self.resume_btn.setEnabled(False)
            else:
                self.status_indicator.setStyleSheet("color: #F44336; font-size: 16px;")
                self.device_state_label.setText(f"Status: {state.status.name}")
                self.stop_btn.setEnabled(False)
                self.resume_btn.setEnabled(True)
        else:
            self.status_label.setText("Not connected")
            self.status_indicator.setStyleSheet("color: #888; font-size: 16px;")
            self.device_info.setText("")
            self.device_state_label.setText("Status: --")
            self.stop_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)

    def _refresh_status(self):
        """Refresh device status"""
        if self._cameo and self._cameo.is_connected:
            self._cameo.refresh_status()

    def set_job(self, job: Optional[CuttingJob]):
        """Set the job to send"""
        self._pending_job = job
        self.send_btn.setEnabled(
            job is not None and
            self._cameo is not None and
            self._cameo.is_connected
        )

    def _on_send_clicked(self):
        """Handle send button click.

        The actual transmission runs in CutWorker (QThread) so the main
        thread — and therefore the UI — stays responsive during cutting.
        """
        if self._pending_job is None or self._cameo is None:
            return

        # Prevent double-sends while a job is in progress
        if self._cut_worker is not None and self._cut_worker.isRunning():
            logger.debug("Send ignored: worker already running")
            return

        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.job_started.emit()

        # *** BLE 競合バグ修正 ***
        # BLE 通信は asyncio._loop.run_until_complete() を使うがスレッドセーフではない。
        # CutWorker（バックグラウンドスレッド）が BLE を使用中に、
        # ステータスリフレッシュタイマー（メインスレッド）も BLE を呼ぶと
        # コマンドが混線し、force/speed が壊れて「非常に濃い動作」が発生する。
        # 送信中はタイマーを停止して BLE アクセスを 1 スレッドに限定する。
        self._refresh_timer.stop()

        self._cut_worker = CutWorker(self._cameo, self._pending_job, self)
        self._cut_worker.progress_updated.connect(self._on_progress_updated)
        self._cut_worker.finished.connect(self._on_worker_finished)
        self._cut_worker.start()

    @pyqtSlot(int, int)
    def _on_progress_updated(self, sent: int, total: int):
        """Update progress bar from the worker thread (signal-safe)."""
        percent = int(sent * 100 / total) if total > 0 else 0
        self.progress_bar.setValue(percent)

    @pyqtSlot(bool)
    def _on_worker_finished(self, success: bool):
        """Called on the main thread when the cut worker finishes."""
        self.progress_bar.setValue(100 if success else 0)
        self.progress_bar.setVisible(False)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._cut_worker = None
        self.job_completed.emit(success)
        # 送信完了後にステータスリフレッシュを再開
        self._refresh_timer.start()

    def _on_test_clicked(self):
        """Handle test cut button click"""
        if self._cameo and self._cameo.is_connected:
            self._cameo.test_cut()

    def _on_home_clicked(self):
        """Send carriage to home position"""
        if self._cameo and self._cameo.is_connected:
            self._cameo.home()
            self.device_state_label.setText("Status: Homing...")

    def _on_load_clicked(self):
        """Feed / load the cutting mat"""
        if self._cameo and self._cameo.is_connected:
            self._cameo.load_media()
            self.device_state_label.setText("Status: Loading media...")

    def _on_unload_clicked(self):
        """Eject / unload the cutting mat"""
        if self._cameo and self._cameo.is_connected:
            self._cameo.unload_media()
            self.device_state_label.setText("Status: Unloading media...")

    @property
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return self._cameo is not None and self._cameo.is_connected

    def get_cameo(self) -> Optional[Cameo5]:
        """Get the Cameo controller"""
        return self._cameo

    def move_to(self, x_su: int, y_su: int, toolholder: int = 2):
        """Move tool to specified position (in SU units)

        Args:
            x_su: X position in SU
            y_su: Y position in SU
            toolholder: Tool holder (1=cutter, 2=pen)
        """
        if self._cameo and self._cameo.is_connected:
            self._cameo.move_to(x_su, y_su, toolholder)

    def _on_stop_clicked(self):
        """Handle stop button click - send escape to stop device"""
        if self._cameo and self._cameo.is_connected:
            self._device_stopped = True
            self._cameo.stop()
            self.device_state_label.setText("Status: Stopped by user")
            self.stop_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)

    def _on_resume_clicked(self):
        """Handle resume button click"""
        if self._cameo and self._cameo.is_connected:
            self._device_stopped = False
            # Re-send the pending job if any
            if self._pending_job:
                self.device_state_label.setText("Status: Resuming...")
                self._on_send_clicked()
            else:
                self.device_state_label.setText("Status: Ready")
            self.resume_btn.setEnabled(False)
